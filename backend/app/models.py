from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class File(Base):
    __tablename__ = "files"
    
    file_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    hash = Column(String, nullable=False)
    imported_at = Column(DateTime, default=datetime.utcnow)
    source_path = Column(String, nullable=False)
    parent_archive_id = Column(Integer, ForeignKey("files.file_id"), nullable=True)
    ingest_state = Column(String, default="pending")  # pending, scanning, parsing, indexing, done, error
    last_offset = Column(Integer, default=0)
    file_type = Column(String, default="moquery")  # moquery, fvTenant, etc.
    
    classes = relationship("Class", back_populates="file")
    ingest_errors = relationship("IngestError", back_populates="file")
    tenant_info = relationship("TenantInfo", back_populates="file")

class Class(Base):
    __tablename__ = "classes"
    
    class_id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.file_id"), nullable=False)
    class_name = Column(String, nullable=False, index=True)
    object_count = Column(Integer, default=0)
    
    file = relationship("File", back_populates="classes")
    objects = relationship("Object", back_populates="class_")

class Object(Base):
    __tablename__ = "objects"
    
    object_id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.class_id"), nullable=False)
    dn = Column(String, nullable=True, index=True)
    line_no = Column(Integer, nullable=False)
    start_byte = Column(Integer, nullable=False)
    end_byte = Column(Integer, nullable=False)
    raw_xml = Column(Text, nullable=False)
    
    class_ = relationship("Class", back_populates="objects")
    attributes = relationship("Attribute", back_populates="object")
    relations = relationship("Relation", back_populates="object")

class Attribute(Base):
    __tablename__ = "attributes"
    
    attr_id = Column(Integer, primary_key=True, index=True)
    object_id = Column(Integer, ForeignKey("objects.object_id"), nullable=False)
    key = Column(String, nullable=False, index=True)
    value = Column(Text, nullable=False)
    
    object = relationship("Object", back_populates="attributes")

class Relation(Base):
    __tablename__ = "relations"
    
    rel_id = Column(Integer, primary_key=True, index=True)
    object_id = Column(Integer, ForeignKey("objects.object_id"), nullable=False)
    rel_type = Column(String, nullable=False)  # dn_attr, etc.
    target_dn = Column(String, nullable=False)
    raw_value = Column(Text, nullable=False)
    
    object = relationship("Object", back_populates="relations")

class IngestError(Base):
    __tablename__ = "ingest_errors"
    
    err_id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.file_id"), nullable=False)
    line_no = Column(Integer, nullable=True)
    offset = Column(Integer, nullable=True)
    excerpt = Column(Text, nullable=False)
    error = Column(Text, nullable=False)
    
    file = relationship("File", back_populates="ingest_errors")

class TenantInfo(Base):
    __tablename__ = "tenant_info"
    
    tenant_id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.file_id"), nullable=False)
    tenant_name = Column(String, nullable=False, index=True)
    tenant_dn = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String)
    last_modified = Column(DateTime)
    uid = Column(String)
    
    file = relationship("File", back_populates="tenant_info")
    tenant_objects = relationship("TenantObject", back_populates="tenant_info")
    search_index = relationship("TenantSearchIndex", back_populates="tenant_info")

class TenantObject(Base):
    __tablename__ = "tenant_objects"
    
    object_id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenant_info.tenant_id"), nullable=False)
    object_type = Column(String, nullable=False, index=True)  # fvAp, fvBD, fvCtx, vzBrCP, l3extOut, etc.
    object_name = Column(String, nullable=False)
    object_dn = Column(String, nullable=False, index=True)
    parent_dn = Column(String, nullable=True, index=True)
    description = Column(Text)
    status = Column(String)
    last_modified = Column(DateTime)
    raw_xml = Column(Text)
    
    tenant_info = relationship("TenantInfo", back_populates="tenant_objects")
    tenant_attributes = relationship("TenantAttribute", back_populates="tenant_object")

class TenantAttribute(Base):
    __tablename__ = "tenant_attributes"
    
    attr_id = Column(Integer, primary_key=True, index=True)
    object_id = Column(Integer, ForeignKey("tenant_objects.object_id"), nullable=False)
    attr_key = Column(String, nullable=False, index=True)
    attr_value = Column(Text, nullable=False)
    is_dn = Column(Boolean, default=False)
    is_ip = Column(Boolean, default=False)
    is_mac = Column(Boolean, default=False)
    
    tenant_object = relationship("TenantObject", back_populates="tenant_attributes")

class TenantSearchIndex(Base):
    __tablename__ = "tenant_search_index"
    
    search_id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenant_info.tenant_id"), nullable=False)
    object_id = Column(Integer, ForeignKey("tenant_objects.object_id"), nullable=False)
    search_type = Column(String, nullable=False, index=True)  # 'mac', 'ip', 'dn', 'name'
    search_value = Column(String, nullable=False, index=True)
    object_reference = Column(String, nullable=False)
    
    tenant_info = relationship("TenantInfo", back_populates="search_index")

Index('idx_objects_class_id', Object.class_id)
Index('idx_attributes_key', Attribute.key)
Index('idx_attributes_object_id', Attribute.object_id)
Index('idx_relations_object_id', Relation.object_id)
Index('idx_tenant_objects_type', TenantObject.object_type)
Index('idx_tenant_objects_dn', TenantObject.object_dn)
Index('idx_tenant_attributes_key', TenantAttribute.attr_key)
Index('idx_tenant_search_type_value', TenantSearchIndex.search_type, TenantSearchIndex.search_value)
