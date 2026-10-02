from pydantic import BaseModel, Field
from typing import Optional
class RegisterIn(BaseModel): name:str; email:str; password:str; role:str='STUDENT'; department_id:Optional[int]=None
class LoginIn(BaseModel): email:str; password:str
class RequestIn(BaseModel): title:str; description:str; privacy_mode:str='NORMAL'
class OverrideIn(BaseModel): category:Optional[str]=None; subcategory:Optional[str]=None; priority:Optional[str]=None; sensitivity_level:Optional[str]=None; primary_department_id:Optional[int]=None; reason:str='Human triage override'
class StatusIn(BaseModel): status:str
class NoteIn(BaseModel): note:str
