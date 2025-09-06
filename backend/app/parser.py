import re
import asyncio
from typing import Dict, List, Tuple, Optional, AsyncGenerator
from dataclasses import dataclass
import xml.etree.ElementTree as ET

@dataclass
class ParsedObject:
    class_name: str
    dn: Optional[str]
    line_no: int
    start_byte: int
    end_byte: int
    raw_xml: str
    attributes: Dict[str, str]
    relations: List[Tuple[str, str, str]]  # (rel_type, target_dn, raw_value)

class MoqueryParser:
    def __init__(self):
        self.class_regex = re.compile(r'<([a-zA-Z0-9_.:]+)\s+')
        self.dn_patterns = [
            re.compile(r'(\w*[Dd]n)\s*=\s*["\']([^"\']+)["\']'),
            re.compile(r'=\s*["\']([^"\']*(?:uni/|topology/)[^"\']*)["\']'),
        ]
        
    async def detect_classes_from_header(self, content: str) -> List[str]:
        """Detect classes from moquery command headers"""
        classes = []
        lines = content.split('\n')[:50]  # Check first 50 lines
        
        for line in lines:
            if 'moquery -c' in line:
                match = re.search(r'moquery\s+-c\s+([a-zA-Z0-9_.:]+)', line)
                if match:
                    classes.append(match.group(1))
        
        return classes
    
    async def stream_parse(self, file_path: str, start_offset: int = 0) -> AsyncGenerator[ParsedObject, None]:
        """Stream parse a file starting from given offset"""
        buffer = ""
        line_no = 1
        byte_offset = start_offset
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            if start_offset > 0:
                f.seek(start_offset)
                f.readline()
                line_no = self._count_lines_up_to_offset(file_path, f.tell())
            
            while True:
                chunk = f.read(8192)  # 8KB chunks
                if not chunk:
                    break
                    
                buffer += chunk
                
                while True:
                    tag_start = buffer.find('<')
                    if tag_start == -1:
                        break
                    
                    tag_end = buffer.find('>', tag_start)
                    if tag_end == -1:
                        break
                    
                    tag_content = buffer[tag_start:tag_end + 1]
                    if tag_content.startswith('</') or tag_content.endswith('/>'):
                        buffer = buffer[tag_end + 1:]
                        continue
                    
                    class_match = self.class_regex.match(tag_content)
                    if not class_match:
                        buffer = buffer[tag_end + 1:]
                        continue
                    
                    class_name = class_match.group(1)
                    
                    next_tag_start = buffer.find('<', tag_end + 1)
                    if next_tag_start == -1:
                        break
                    
                    obj_content = buffer[tag_start:next_tag_start].strip()
                    if not obj_content:
                        buffer = buffer[tag_end + 1:]
                        continue
                    
                    try:
                        parsed_obj = await self._parse_object(
                            class_name, obj_content, line_no, 
                            byte_offset + tag_start, byte_offset + next_tag_start
                        )
                        if parsed_obj:
                            yield parsed_obj
                    except Exception as e:
                        print(f"Parse error at line {line_no}: {e}")
                    
                    line_no += obj_content.count('\n')
                    buffer = buffer[next_tag_start:]
                
                byte_offset += len(chunk)
                
                if byte_offset % 100000 == 0:  # Every 100KB
                    await asyncio.sleep(0)
    
    async def _parse_object(self, class_name: str, content: str, line_no: int, 
                          start_byte: int, end_byte: int) -> Optional[ParsedObject]:
        """Parse a single object from XML content"""
        try:
            attributes = {}
            dn = None
            relations = []
            
            attr_pattern = re.compile(r'(\w+)\s*=\s*["\']([^"\']*)["\']')
            for match in attr_pattern.finditer(content):
                key, value = match.groups()
                attributes[key] = value
                
                if key.lower().endswith('dn') or value.startswith(('uni/', 'topology/')):
                    if not dn:  # Use first DN found
                        dn = value
                    relations.append(('dn_attr', value, f'{key}="{value}"'))
            
            return ParsedObject(
                class_name=class_name,
                dn=dn,
                line_no=line_no,
                start_byte=start_byte,
                end_byte=end_byte,
                raw_xml=content,
                attributes=attributes,
                relations=relations
            )
            
        except Exception as e:
            print(f"Error parsing object: {e}")
            return None
    
    def _count_lines_up_to_offset(self, file_path: str, offset: int) -> int:
        """Count lines up to a given byte offset"""
        line_count = 1
        with open(file_path, 'rb') as f:
            while f.tell() < offset:
                chunk = f.read(8192)
                if not chunk:
                    break
                line_count += chunk.count(b'\n')
        return line_count
