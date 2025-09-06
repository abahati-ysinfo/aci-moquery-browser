import re
import asyncio
from typing import Dict, List, Tuple, Optional, AsyncGenerator
from dataclasses import dataclass
import xml.etree.ElementTree as ET
from datetime import datetime
import ipaddress

@dataclass
class TenantObjectData:
    object_type: str
    object_name: str
    object_dn: str
    parent_dn: Optional[str]
    description: Optional[str]
    status: Optional[str]
    last_modified: Optional[datetime]
    raw_xml: str
    attributes: Dict[str, str]
    search_entries: List[Tuple[str, str]]  # (search_type, search_value)

class TenantParser:
    def __init__(self):
        self.tenant_objects = [
            'fvTenant', 'fvAp', 'fvAEPg', 'fvBD', 'fvCtx', 'fvSubnet',
            'vzBrCP', 'vzSubj', 'vzFilter', 'vzEntry',
            'l3extOut', 'l3extLNodeP', 'l3extRsNodeL3OutAtt', 'l3extInstP',
            'ospfExtP', 'bgpExtP', 'eigrpExtP',
            'fvCEp', 'fvIp', 'fvRsCEpToPathEp'
        ]
        self.mac_pattern = re.compile(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})')
        self.ip_pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?:/[0-9]{1,2})?\b')
        self.dn_pattern = re.compile(r'uni/[^"\']*')
        
    async def detect_tenant_file(self, file_path: str) -> bool:
        """Detect if file contains fvTenant data"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(10000)  # Check first 10KB
                return '<fvTenant' in content and 'moquery -c fvTenant' in content
        except Exception:
            return False
    
    async def parse_tenant_file(self, file_path: str) -> AsyncGenerator[TenantObjectData, None]:
        """Parse fvTenant file and yield tenant objects"""
        buffer = ""
        current_tenant = None
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            while True:
                chunk = f.read(16384)  # 16KB chunks
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
                    
                    if tag_content.startswith('</'):
                        if '</fvTenant>' in tag_content:
                            current_tenant = None
                        buffer = buffer[tag_end + 1:]
                        continue
                    
                    if tag_content.endswith('/>'):
                        obj_data = await self._parse_single_tag(tag_content, current_tenant)
                        if obj_data:
                            yield obj_data
                        buffer = buffer[tag_end + 1:]
                        continue
                    
                    next_close_tag = self._find_matching_close_tag(buffer, tag_start)
                    if next_close_tag == -1:
                        break
                    
                    full_element = buffer[tag_start:next_close_tag]
                    obj_data = await self._parse_full_element(full_element, current_tenant)
                    if obj_data:
                        if obj_data.object_type == 'fvTenant':
                            current_tenant = obj_data.object_dn
                        yield obj_data
                    
                    buffer = buffer[next_close_tag:]
                
                await asyncio.sleep(0)  # Yield control
    
    async def _parse_single_tag(self, tag_content: str, current_tenant: Optional[str]) -> Optional[TenantObjectData]:
        """Parse self-closing XML tag"""
        try:
            root = ET.fromstring(tag_content)
            return await self._extract_object_data(root, tag_content, current_tenant)
        except Exception as e:
            print(f"Error parsing single tag: {e}")
            return None
    
    async def _parse_full_element(self, element_content: str, current_tenant: Optional[str]) -> Optional[TenantObjectData]:
        """Parse full XML element with potential children"""
        try:
            root = ET.fromstring(element_content)
            return await self._extract_object_data(root, element_content, current_tenant)
        except Exception as e:
            print(f"Error parsing full element: {e}")
            return None
    
    async def _extract_object_data(self, element: ET.Element, raw_xml: str, current_tenant: Optional[str]) -> Optional[TenantObjectData]:
        """Extract object data from XML element"""
        object_type = element.tag
        
        if object_type not in self.tenant_objects:
            return None
        
        attributes = element.attrib
        object_name = attributes.get('name', '')
        object_dn = attributes.get('dn', '')
        
        parent_dn = None
        if object_dn and '/' in object_dn:
            parent_dn = '/'.join(object_dn.split('/')[:-1])
        
        description = attributes.get('descr', '')
        status = attributes.get('status', '')
        
        last_modified = None
        if 'modTs' in attributes:
            try:
                last_modified = datetime.fromisoformat(attributes['modTs'].replace('+10:00', '+10:00'))
            except:
                pass
        
        search_entries = []
        
        for key, value in attributes.items():
            if self.mac_pattern.search(value):
                search_entries.append(('mac', value))
            
            if self.ip_pattern.search(value):
                for match in self.ip_pattern.finditer(value):
                    search_entries.append(('ip', match.group()))
            
            if self.dn_pattern.search(value) or key.lower().endswith('dn'):
                search_entries.append(('dn', value))
        
        if object_name:
            search_entries.append(('name', object_name))
        
        return TenantObjectData(
            object_type=object_type,
            object_name=object_name,
            object_dn=object_dn,
            parent_dn=parent_dn,
            description=description,
            status=status,
            last_modified=last_modified,
            raw_xml=raw_xml,
            attributes=attributes,
            search_entries=search_entries
        )
    
    def _find_matching_close_tag(self, buffer: str, start_pos: int) -> int:
        """Find the matching closing tag for an opening tag"""
        tag_start = buffer.find('<', start_pos)
        if tag_start == -1:
            return -1
        
        tag_name_end = buffer.find(' ', tag_start)
        tag_end = buffer.find('>', tag_start)
        
        if tag_name_end == -1 or tag_name_end > tag_end:
            tag_name_end = tag_end
        
        tag_name = buffer[tag_start + 1:tag_name_end]
        close_tag = f'</{tag_name}>'
        
        close_pos = buffer.find(close_tag, tag_end)
        if close_pos != -1:
            return close_pos + len(close_tag)
        
        return -1
    
    def get_user_friendly_headers(self, object_type: str) -> Dict[str, str]:
        """Get user-friendly column headers for object type"""
        base_headers = {
            'name': 'Name',
            'descr': 'Description',
            'dn': 'Distinguished Name',
            'status': 'Status',
            'modTs': 'Last Modified',
            'uid': 'User ID',
            'lcOwn': 'Local Owner',
            'monPolDn': 'Monitoring Policy'
        }
        
        type_specific_headers = {
            'fvTenant': {
                'nameAlias': 'Name Alias',
                'ownerKey': 'Owner Key',
                'ownerTag': 'Owner Tag'
            },
            'fvAp': {
                'prio': 'Priority'
            },
            'fvBD': {
                'arpFlood': 'ARP Flooding',
                'unicastRoute': 'Unicast Routing',
                'unkMacUcastAct': 'Unknown MAC Action',
                'unkMcastAct': 'Unknown Multicast Action',
                'mtu': 'MTU',
                'seg': 'Segment ID',
                'scope': 'Network Scope',
                'pcTag': 'Policy Tag'
            },
            'fvCtx': {
                'seg': 'Segment ID',
                'scope': 'Network Scope',
                'pcTag': 'Policy Tag',
                'pcEnfPref': 'Policy Enforcement'
            },
            'vzBrCP': {
                'scope': 'Contract Scope',
                'prio': 'Priority',
                'targetDscp': 'DSCP Marking',
                'intent': 'Intent'
            },
            'l3extOut': {
                'enforceRtctrl': 'Route Control',
                'targetDscp': 'DSCP Marking'
            },
            'ospfExtP': {
                'areaCost': 'OSPF Area Cost',
                'areaId': 'OSPF Area ID',
                'areaType': 'OSPF Area Type',
                'multipodInternal': 'Multi-Pod Internal'
            }
        }
        
        headers = base_headers.copy()
        if object_type in type_specific_headers:
            headers.update(type_specific_headers[object_type])
        
        return headers
