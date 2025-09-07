from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update
from typing import List, Optional, Dict, Any
import os
import hashlib
import json
import csv
import io
from datetime import datetime

from .database import get_db, init_db
from .models import File as FileModel, Class, Object, Attribute, Relation, IngestError, TenantInfo, TenantObject, TenantAttribute, TenantSearchIndex
from .ingest import ingest_manager
from .tenant_parser import TenantParser

app = FastAPI(title="ACI Moquery Log Browser", version="1.0.0")

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    chunk_number: int = Query(0),
    total_chunks: int = Query(1),
    db: AsyncSession = Depends(get_db)
):
    """Upload file in chunks"""
    try:
        upload_dir = "./data/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        
        result = await db.execute(
            select(FileModel).where(FileModel.hash == file_hash)
        )
        existing_file = result.scalar_one_or_none()
        
        if existing_file:
            return {
                "file_id": existing_file.file_id,
                "message": "File already exists",
                "status": "duplicate"
            }
        
        file_path = os.path.join(upload_dir, f"{file_hash}_{file.filename}")
        
        if chunk_number == 0:
            with open(file_path, "wb") as f:
                f.write(content)
        else:
            with open(file_path, "ab") as f:
                f.write(content)
        
        if chunk_number == total_chunks - 1:
            file_size = os.path.getsize(file_path)
            
            file_type = "moquery"  # default
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    first_few_lines = f.read(1024)  # Read first 1KB
                    if 'fvTenant' in first_few_lines or 'moquery -c fvTenant' in first_few_lines:
                        file_type = "fvTenant"
            except Exception:
                pass  # Keep default if reading fails
            
            db_file = FileModel(
                name=file.filename,
                size=file_size,
                hash=file_hash,
                source_path=file_path,
                ingest_state="uploaded",
                file_type=file_type
            )
            db.add(db_file)
            await db.commit()
            await db.refresh(db_file)
            
            return {
                "file_id": db_file.file_id,
                "message": "Upload complete",
                "status": "uploaded"
            }
        else:
            return {
                "message": f"Chunk {chunk_number + 1}/{total_chunks} uploaded",
                "status": "uploading"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/complete")
async def complete_upload(
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Finalize upload and start ingest"""
    try:
        result = await db.execute(
            select(FileModel).where(FileModel.file_id == file_id)
        )
        file_obj = result.scalar_one_or_none()
        
        if not file_obj:
            raise HTTPException(status_code=404, detail="File not found")
        
        tenant_parser = TenantParser()
        if await tenant_parser.detect_tenant_file(file_obj.source_path):
            await db.execute(
                update(FileModel).where(FileModel.file_id == file_id)
                .values(file_type="fvTenant")
            )
            await db.commit()
        
        success = await ingest_manager.start_ingest(file_id)
        
        if success:
            return {"message": "Ingest started", "status": "ingesting"}
        else:
            return {"message": "Ingest queue full, try again later", "status": "queued"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ingest/status")
async def get_ingest_status(
    file_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get ingest status for file(s)"""
    try:
        if file_id:
            return await ingest_manager.get_ingest_status(file_id)
        else:
            result = await db.execute(select(FileModel))
            files = result.scalars().all()
            
            statuses = []
            for file_obj in files:
                status = await ingest_manager.get_ingest_status(file_obj.file_id)
                statuses.append(status)
            
            return {"files": statuses}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ingest/cancel")
async def cancel_ingest(
    file_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Cancel active ingest"""
    try:
        success = await ingest_manager.cancel_ingest(file_id)
        
        if success:
            return {"message": "Ingest cancelled", "status": "cancelled"}
        else:
            return {"message": "No active ingest found", "status": "not_active"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files")
async def list_files(db: AsyncSession = Depends(get_db)):
    """List all uploaded files with their classes and status"""
    try:
        result = await db.execute(
            select(FileModel).order_by(FileModel.imported_at.desc())
        )
        files = result.scalars().all()
        
        file_list = []
        for file_obj in files:
            class_result = await db.execute(
                select(Class).where(Class.file_id == file_obj.file_id)
            )
            classes = class_result.scalars().all()
            
            file_list.append({
                "file_id": file_obj.file_id,
                "name": file_obj.name,
                "size": file_obj.size,
                "imported_at": file_obj.imported_at.isoformat(),
                "ingest_state": file_obj.ingest_state,
                "file_type": file_obj.file_type,
                "classes": [
                    {
                        "class_id": cls.class_id,
                        "class_name": cls.class_name,
                        "object_count": cls.object_count
                    }
                    for cls in classes
                ]
            })
        
        return {"files": file_list}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/classes")
async def list_classes(
    file_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """List classes with counts"""
    try:
        query = select(Class)
        if file_id:
            query = query.where(Class.file_id == file_id)
        
        result = await db.execute(query.order_by(Class.class_name))
        classes = result.scalars().all()
        
        return {
            "classes": [
                {
                    "class_id": cls.class_id,
                    "file_id": cls.file_id,
                    "class_name": cls.class_name,
                    "object_count": cls.object_count
                }
                for cls in classes
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/objects")
async def list_objects(
    class_name: Optional[str] = Query(None),
    file_id: Optional[int] = Query(None),
    filter: Optional[str] = Query(None),
    order_by: str = Query("object_id"),
    dir: str = Query("asc"),
    limit: int = Query(100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db)
):
    """List objects with server-side pagination, filtering, and sorting"""
    try:
        query = select(Object).join(Class)
        
        conditions = []
        if class_name:
            conditions.append(Class.class_name == class_name)
        if file_id:
            conditions.append(Class.file_id == file_id)
        if filter:
            conditions.append(
                or_(
                    Object.dn.contains(filter),
                    Object.raw_xml.contains(filter)
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        order_column = getattr(Object, order_by, Object.object_id)
        if dir.lower() == "desc":
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())
        
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total_count = count_result.scalar()
        
        query = query.offset(offset).limit(limit)
        
        result = await db.execute(query)
        objects = result.scalars().all()
        
        return {
            "objects": [
                {
                    "object_id": obj.object_id,
                    "class_id": obj.class_id,
                    "dn": obj.dn,
                    "line_no": obj.line_no,
                    "start_byte": obj.start_byte,
                    "end_byte": obj.end_byte,
                    "raw_xml": obj.raw_xml[:500] + "..." if len(obj.raw_xml) > 500 else obj.raw_xml
                }
                for obj in objects
            ],
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/objects/{object_id}")
async def get_object_detail(
    object_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed object information with attributes and relations"""
    try:
        obj_result = await db.execute(
            select(Object).where(Object.object_id == object_id)
        )
        obj = obj_result.scalar_one_or_none()
        
        if not obj:
            raise HTTPException(status_code=404, detail="Object not found")
        
        attr_result = await db.execute(
            select(Attribute).where(Attribute.object_id == object_id)
        )
        attributes = attr_result.scalars().all()
        
        rel_result = await db.execute(
            select(Relation).where(Relation.object_id == object_id)
        )
        relations = rel_result.scalars().all()
        
        return {
            "object": {
                "object_id": obj.object_id,
                "class_id": obj.class_id,
                "dn": obj.dn,
                "line_no": obj.line_no,
                "start_byte": obj.start_byte,
                "end_byte": obj.end_byte,
                "raw_xml": obj.raw_xml
            },
            "attributes": [
                {
                    "attr_id": attr.attr_id,
                    "key": attr.key,
                    "value": attr.value
                }
                for attr in attributes
            ],
            "relations": [
                {
                    "rel_id": rel.rel_id,
                    "rel_type": rel.rel_type,
                    "target_dn": rel.target_dn,
                    "raw_value": rel.raw_value
                }
                for rel in relations
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/attributes")
async def get_attributes(
    object_ids: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Get attributes for multiple objects"""
    try:
        object_id_list = [int(x.strip()) for x in object_ids.split(",")]
        
        result = await db.execute(
            select(Attribute).where(Attribute.object_id.in_(object_id_list))
        )
        attributes = result.scalars().all()
        
        grouped = {}
        for attr in attributes:
            if attr.object_id not in grouped:
                grouped[attr.object_id] = []
            grouped[attr.object_id].append({
                "attr_id": attr.attr_id,
                "key": attr.key,
                "value": attr.value
            })
        
        return {"attributes": grouped}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/relations")
async def get_relations(
    class_name: Optional[str] = Query(None),
    object_ids: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get relations for objects"""
    try:
        query = select(Relation).join(Object).join(Class)
        
        conditions = []
        if class_name:
            conditions.append(Class.class_name == class_name)
        if object_ids:
            object_id_list = [int(x.strip()) for x in object_ids.split(",")]
            conditions.append(Relation.object_id.in_(object_id_list))
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await db.execute(query)
        relations = result.scalars().all()
        
        return {
            "relations": [
                {
                    "rel_id": rel.rel_id,
                    "object_id": rel.object_id,
                    "rel_type": rel.rel_type,
                    "target_dn": rel.target_dn,
                    "raw_value": rel.raw_value
                }
                for rel in relations
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/raw/{file_id}")
async def get_raw_content(
    file_id: int,
    start_byte: int = Query(0),
    end_byte: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Stream raw file content by byte range"""
    try:
        result = await db.execute(
            select(FileModel).where(FileModel.file_id == file_id)
        )
        file_obj = result.scalar_one_or_none()
        
        if not file_obj:
            raise HTTPException(status_code=404, detail="File not found")
        
        def generate():
            with open(file_obj.source_path, 'rb') as f:
                f.seek(start_byte)
                bytes_to_read = (end_byte - start_byte) if end_byte else 8192
                
                while bytes_to_read > 0:
                    chunk_size = min(8192, bytes_to_read)
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
                    if end_byte:
                        bytes_to_read -= len(chunk)
        
        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={
                "Content-Disposition": f"inline; filename={file_obj.name}"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export")
async def export_data(
    class_name: Optional[str] = Query(None),
    file_id: Optional[int] = Query(None),
    format: str = Query("csv"),
    filter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Export current filtered data as CSV or JSON"""
    try:
        query = select(Object).join(Class)
        
        conditions = []
        if class_name:
            conditions.append(Class.class_name == class_name)
        if file_id:
            conditions.append(Class.file_id == file_id)
        if filter:
            conditions.append(
                or_(
                    Object.dn.contains(filter),
                    Object.raw_xml.contains(filter)
                )
            )
        
        if conditions:
            query = query.where(and_(*conditions))
        
        result = await db.execute(query)
        objects = result.scalars().all()
        
        if format.lower() == "json":
            data = [
                {
                    "object_id": obj.object_id,
                    "class_id": obj.class_id,
                    "dn": obj.dn,
                    "line_no": obj.line_no,
                    "start_byte": obj.start_byte,
                    "end_byte": obj.end_byte,
                    "raw_xml": obj.raw_xml
                }
                for obj in objects
            ]
            
            output = io.StringIO()
            json.dump(data, output, indent=2)
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"}
            )
        
        else:  # CSV format
            output = io.StringIO()
            writer = csv.writer(output)
            
            writer.writerow(["object_id", "class_id", "dn", "line_no", "start_byte", "end_byte", "raw_xml"])
            
            for obj in objects:
                writer.writerow([
                    obj.object_id,
                    obj.class_id,
                    obj.dn,
                    obj.line_no,
                    obj.start_byte,
                    obj.end_byte,
                    obj.raw_xml
                ])
            
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
            )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
async def get_config():
    """Get current configuration"""
    return {
        "max_concurrent_ingests": ingest_manager.max_concurrent_ingests,
        "batch_size": ingest_manager.batch_size,
        "data_directory": "./data",
        "upload_chunk_size": "8MB",
        "max_file_size": "200MB"
    }

@app.post("/api/config")
async def update_config(config: Dict[str, Any]):
    """Update configuration"""
    try:
        if "max_concurrent_ingests" in config:
            ingest_manager.max_concurrent_ingests = config["max_concurrent_ingests"]
        if "batch_size" in config:
            ingest_manager.batch_size = config["batch_size"]
        
        return {"message": "Configuration updated", "config": await get_config()}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tenant-info")
async def get_tenant_info(
    file_id: int = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Get tenant information for a file"""
    try:
        result = await db.execute(
            select(TenantInfo).where(TenantInfo.file_id == file_id)
        )
        tenants = result.scalars().all()
        
        return {
            "tenants": [
                {
                    "tenant_id": tenant.tenant_id,
                    "tenant_name": tenant.tenant_name,
                    "tenant_dn": tenant.tenant_dn,
                    "description": tenant.description,
                    "status": tenant.status,
                    "last_modified": tenant.last_modified.isoformat() if tenant.last_modified else None,
                    "uid": tenant.uid
                }
                for tenant in tenants
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tenant-objects")
async def get_tenant_objects(
    file_id: int = Query(...),
    object_type: Optional[str] = Query(None),
    tenant_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db)
):
    """Get tenant objects with filtering and pagination"""
    try:
        query = select(TenantObject).join(TenantInfo).where(TenantInfo.file_id == file_id)
        
        if object_type:
            query = query.where(TenantObject.object_type == object_type)
        if tenant_id:
            query = query.where(TenantObject.tenant_id == tenant_id)
        if search:
            query = query.where(
                or_(
                    TenantObject.object_name.contains(search),
                    TenantObject.object_dn.contains(search),
                    TenantObject.description.contains(search)
                )
            )
        
        count_result = await db.execute(select(func.count()).select_from(query.subquery()))
        total_count = count_result.scalar()
        
        result = await db.execute(query.offset(offset).limit(limit))
        objects = result.scalars().all()
        
        return {
            "objects": [
                {
                    "object_id": obj.object_id,
                    "tenant_id": obj.tenant_id,
                    "object_type": obj.object_type,
                    "object_name": obj.object_name,
                    "object_dn": obj.object_dn,
                    "parent_dn": obj.parent_dn,
                    "description": obj.description,
                    "status": obj.status,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None
                }
                for obj in objects
            ],
            "total_count": total_count,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tenant-search")
async def search_tenant_data(
    file_id: int = Query(...),
    search_type: str = Query(...),
    search_value: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Advanced search for tenant data by MAC/IP addresses"""
    try:
        query = select(TenantSearchIndex, TenantObject).join(
            TenantObject, TenantSearchIndex.object_id == TenantObject.object_id
        ).join(TenantInfo).where(
            TenantInfo.file_id == file_id,
            TenantSearchIndex.search_type == search_type,
            TenantSearchIndex.search_value.contains(search_value)
        )
        
        result = await db.execute(query)
        search_results = result.all()
        
        return {
            "results": [
                {
                    "search_entry": {
                        "search_type": search_entry.search_type,
                        "search_value": search_entry.search_value,
                        "object_reference": search_entry.object_reference
                    },
                    "object": {
                        "object_id": tenant_obj.object_id,
                        "object_type": tenant_obj.object_type,
                        "object_name": tenant_obj.object_name,
                        "object_dn": tenant_obj.object_dn,
                        "description": tenant_obj.description
                    }
                }
                for search_entry, tenant_obj in search_results
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tenant-export")
async def export_tenant_data(
    file_id: int = Query(...),
    object_type: str = Query(...),
    format: str = Query("csv"),
    db: AsyncSession = Depends(get_db)
):
    """Export tenant data as CSV"""
    try:
        query = select(TenantObject, TenantAttribute).join(
            TenantAttribute, TenantObject.object_id == TenantAttribute.object_id
        ).join(TenantInfo).where(
            TenantInfo.file_id == file_id,
            TenantObject.object_type == object_type
        )
        
        result = await db.execute(query)
        data = result.all()
        
        objects_data = {}
        for tenant_obj, tenant_attr in data:
            if tenant_obj.object_id not in objects_data:
                objects_data[tenant_obj.object_id] = {
                    'object': tenant_obj,
                    'attributes': {}
                }
            objects_data[tenant_obj.object_id]['attributes'][tenant_attr.attr_key] = tenant_attr.attr_value
        
        output = io.StringIO()
        if objects_data:
            all_keys = set()
            for obj_data in objects_data.values():
                all_keys.update(obj_data['attributes'].keys())
            
            headers = ['object_name', 'object_dn', 'description', 'status'] + sorted(all_keys)
            writer = csv.writer(output)
            writer.writerow(headers)
            
            for obj_data in objects_data.values():
                obj = obj_data['object']
                attrs = obj_data['attributes']
                row = [
                    obj.object_name,
                    obj.object_dn,
                    obj.description,
                    obj.status
                ] + [attrs.get(key, '') for key in sorted(all_keys)]
                writer.writerow(row)
        
        output.seek(0)
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=tenant_{object_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
