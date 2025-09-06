import asyncio
import hashlib
import os
import zipfile
import tarfile
import py7zr
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from .models import File, Class, Object, Attribute, Relation, IngestError, TenantInfo, TenantObject, TenantAttribute, TenantSearchIndex
from .parser import MoqueryParser, ParsedObject
from .tenant_parser import TenantParser
from .database import AsyncSessionLocal

class IngestManager:
    def __init__(self, max_concurrent_ingests: int = 2, batch_size: int = 2000):
        self.max_concurrent_ingests = max_concurrent_ingests
        self.batch_size = batch_size
        self.active_ingests: Dict[int, asyncio.Task] = {}
        self.parser = MoqueryParser()
        
    async def start_ingest(self, file_id: int) -> bool:
        """Start ingesting a file"""
        if len(self.active_ingests) >= self.max_concurrent_ingests:
            return False
            
        if file_id in self.active_ingests:
            return False
            
        task = asyncio.create_task(self._ingest_file(file_id))
        self.active_ingests[file_id] = task
        
        def cleanup(task):
            if file_id in self.active_ingests:
                del self.active_ingests[file_id]
        
        task.add_done_callback(cleanup)
        return True
    
    async def cancel_ingest(self, file_id: int) -> bool:
        """Cancel an active ingest"""
        if file_id not in self.active_ingests:
            return False
            
        task = self.active_ingests[file_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
            
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(File).where(File.file_id == file_id).values(ingest_state="cancelled")
            )
            await session.commit()
            
        return True
    
    async def get_ingest_status(self, file_id: int) -> Dict:
        """Get ingest status for a file"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(File).where(File.file_id == file_id)
            )
            file_obj = result.scalar_one_or_none()
            
            if not file_obj:
                return {"error": "File not found"}
            
            class_result = await session.execute(
                select(Class).where(Class.file_id == file_id)
            )
            classes = class_result.scalars().all()
            
            total_objects = sum(cls.object_count for cls in classes)
            
            error_result = await session.execute(
                select(IngestError).where(IngestError.file_id == file_id)
            )
            error_count = len(error_result.scalars().all())
            
            return {
                "file_id": file_id,
                "name": file_obj.name,
                "size": file_obj.size,
                "state": file_obj.ingest_state,
                "last_offset": file_obj.last_offset,
                "progress_percent": (file_obj.last_offset / file_obj.size * 100) if file_obj.size > 0 else 0,
                "classes_found": len(classes),
                "total_objects": total_objects,
                "error_count": error_count,
                "is_active": file_id in self.active_ingests
            }
    
    async def _ingest_file(self, file_id: int):
        """Main ingest process for a file"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(File).where(File.file_id == file_id)
            )
            file_obj = result.scalar_one_or_none()
            
            if not file_obj:
                return
            
            try:
                await session.execute(
                    update(File).where(File.file_id == file_id).values(ingest_state="scanning")
                )
                await session.commit()
                
                file_path = await self._prepare_file(file_obj)
                
                await session.execute(
                    update(File).where(File.file_id == file_id).values(ingest_state="parsing")
                )
                await session.commit()
                
                if file_obj.file_type == "fvTenant":
                    await self._parse_and_ingest_tenant(session, file_obj, file_path)
                else:
                    await self._parse_and_ingest(session, file_obj, file_path)
                
                await session.execute(
                    update(File).where(File.file_id == file_id).values(ingest_state="indexing")
                )
                await session.commit()
                
                await self._create_indexes(session, file_id)
                
                await session.execute(
                    update(File).where(File.file_id == file_id).values(ingest_state="done")
                )
                await session.commit()
                
            except Exception as e:
                await session.execute(
                    update(File).where(File.file_id == file_id).values(ingest_state="error")
                )
                await session.commit()
                
                error_obj = IngestError(
                    file_id=file_id,
                    excerpt=str(e)[:1000],
                    error=f"Ingest failed: {str(e)}"
                )
                session.add(error_obj)
                await session.commit()
                
                raise
    
    async def _prepare_file(self, file_obj: File) -> str:
        """Extract archive if needed, return path to text file"""
        file_path = file_obj.source_path
        
        if file_path.endswith(('.zip', '.7z', '.tar.gz', '.tgz')):
            extract_dir = f"./data/extracted/{file_obj.file_id}"
            os.makedirs(extract_dir, exist_ok=True)
            
            if file_path.endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            elif file_path.endswith('.7z'):
                with py7zr.SevenZipFile(file_path, mode='r') as archive:
                    archive.extractall(extract_dir)
            elif file_path.endswith(('.tar.gz', '.tgz')):
                with tarfile.open(file_path, 'r:gz') as tar_ref:
                    tar_ref.extractall(extract_dir)
            
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file.endswith(('.txt', '.log')):
                        return os.path.join(root, file)
            
            raise ValueError("No text files found in archive")
        
        return file_path
    
    async def _parse_and_ingest(self, session: AsyncSession, file_obj: File, file_path: str):
        """Parse file and ingest data in batches"""
        class_cache = {}
        object_batch = []
        attribute_batch = []
        relation_batch = []
        
        async for parsed_obj in self.parser.stream_parse(file_path, file_obj.last_offset):
            try:
                if parsed_obj.class_name not in class_cache:
                    result = await session.execute(
                        select(Class).where(
                            Class.file_id == file_obj.file_id,
                            Class.class_name == parsed_obj.class_name
                        )
                    )
                    class_obj = result.scalar_one_or_none()
                    
                    if not class_obj:
                        class_obj = Class(
                            file_id=file_obj.file_id,
                            class_name=parsed_obj.class_name,
                            object_count=0
                        )
                        session.add(class_obj)
                        await session.flush()
                    
                    class_cache[parsed_obj.class_name] = class_obj
                
                class_obj = class_cache[parsed_obj.class_name]
                
                obj = Object(
                    class_id=class_obj.class_id,
                    dn=parsed_obj.dn,
                    line_no=parsed_obj.line_no,
                    start_byte=parsed_obj.start_byte,
                    end_byte=parsed_obj.end_byte,
                    raw_xml=parsed_obj.raw_xml
                )
                object_batch.append(obj)
                
                for key, value in parsed_obj.attributes.items():
                    attribute_batch.append({
                        'key': key,
                        'value': value
                    })
                
                for rel_type, target_dn, raw_value in parsed_obj.relations:
                    relation_batch.append({
                        'rel_type': rel_type,
                        'target_dn': target_dn,
                        'raw_value': raw_value
                    })
                
                if len(object_batch) >= self.batch_size:
                    await self._commit_batch(session, object_batch, attribute_batch, relation_batch, class_cache)
                    object_batch.clear()
                    attribute_batch.clear()
                    relation_batch.clear()
                    
                    await session.execute(
                        update(File).where(File.file_id == file_obj.file_id)
                        .values(last_offset=parsed_obj.end_byte)
                    )
                    await session.commit()
                
            except Exception as e:
                error_obj = IngestError(
                    file_id=file_obj.file_id,
                    line_no=parsed_obj.line_no if 'parsed_obj' in locals() else None,
                    offset=parsed_obj.start_byte if 'parsed_obj' in locals() else None,
                    excerpt=str(parsed_obj.raw_xml)[:500] if 'parsed_obj' in locals() else "Unknown",
                    error=str(e)
                )
                session.add(error_obj)
        
        if object_batch:
            await self._commit_batch(session, object_batch, attribute_batch, relation_batch, class_cache)
    
    async def _commit_batch(self, session: AsyncSession, object_batch: List[Object], 
                          attribute_batch: List[Dict], relation_batch: List[Dict], 
                          class_cache: Dict):
        """Commit a batch of objects with their attributes and relations"""
        session.add_all(object_batch)
        await session.flush()
        
        for i, obj in enumerate(object_batch):
            for j in range(len(attribute_batch)):
                if j < len(attribute_batch):  # Safety check
                    attr_data = attribute_batch[j]
                    attr = Attribute(
                        object_id=obj.object_id,
                        key=attr_data['key'],
                        value=attr_data['value']
                    )
                    session.add(attr)
        
        for i, obj in enumerate(object_batch):
            for j in range(len(relation_batch)):
                if j < len(relation_batch):  # Safety check
                    rel_data = relation_batch[j]
                    rel = Relation(
                        object_id=obj.object_id,
                        rel_type=rel_data['rel_type'],
                        target_dn=rel_data['target_dn'],
                        raw_value=rel_data['raw_value']
                    )
                    session.add(rel)
        
        for class_name, class_obj in class_cache.items():
            class_obj.object_count += len([obj for obj in object_batch if obj.class_id == class_obj.class_id])
        
        await session.commit()
    
    async def _create_indexes(self, session: AsyncSession, file_id: int):
        """Create post-ingest indexes for performance"""
        pass
    
    async def _parse_and_ingest_tenant(self, session: AsyncSession, file_obj: File, file_path: str):
        """Parse tenant file and ingest tenant-specific data"""
        tenant_parser = TenantParser()
        tenant_cache = {}
        
        async for tenant_obj_data in tenant_parser.parse_tenant_file(file_path):
            try:
                if tenant_obj_data.object_type == 'fvTenant':
                    if tenant_obj_data.object_name not in tenant_cache:
                        tenant_info = TenantInfo(
                            file_id=file_obj.file_id,
                            tenant_name=tenant_obj_data.object_name,
                            tenant_dn=tenant_obj_data.object_dn,
                            description=tenant_obj_data.description,
                            status=tenant_obj_data.status,
                            last_modified=tenant_obj_data.last_modified,
                            uid=tenant_obj_data.attributes.get('uid')
                        )
                        session.add(tenant_info)
                        await session.flush()
                        tenant_cache[tenant_obj_data.object_name] = tenant_info
                
                parent_tenant = None
                for tenant_name, tenant_info in tenant_cache.items():
                    if tenant_obj_data.object_dn.startswith(f"uni/tn-{tenant_name}"):
                        parent_tenant = tenant_info
                        break
                
                if parent_tenant:
                    tenant_object = TenantObject(
                        tenant_id=parent_tenant.tenant_id,
                        object_type=tenant_obj_data.object_type,
                        object_name=tenant_obj_data.object_name,
                        object_dn=tenant_obj_data.object_dn,
                        parent_dn=tenant_obj_data.parent_dn,
                        description=tenant_obj_data.description,
                        status=tenant_obj_data.status,
                        last_modified=tenant_obj_data.last_modified,
                        raw_xml=tenant_obj_data.raw_xml
                    )
                    session.add(tenant_object)
                    await session.flush()
                    
                    for key, value in tenant_obj_data.attributes.items():
                        tenant_attr = TenantAttribute(
                            object_id=tenant_object.object_id,
                            attr_key=key,
                            attr_value=value,
                            is_dn=key.lower().endswith('dn') or value.startswith('uni/'),
                            is_ip='.' in value and any(c.isdigit() for c in value),
                            is_mac=':' in value and len(value.replace(':', '')) == 12
                        )
                        session.add(tenant_attr)
                    
                    for search_type, search_value in tenant_obj_data.search_entries:
                        search_entry = TenantSearchIndex(
                            tenant_id=parent_tenant.tenant_id,
                            object_id=tenant_object.object_id,
                            search_type=search_type,
                            search_value=search_value,
                            object_reference=f"{tenant_obj_data.object_type}:{tenant_obj_data.object_name}"
                        )
                        session.add(search_entry)
                
                await session.commit()
                
            except Exception as e:
                print(f"Error processing tenant object: {e}")
                continue

ingest_manager = IngestManager()
