import os
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from .db import get_db
from .models import User
load_dotenv()
SECRET_KEY=os.getenv('SECRET_KEY','dev-secret-change-me')
ALGORITHM='HS256'
EXPIRE=int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES','480'))
pwd=CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2=OAuth2PasswordBearer(tokenUrl='/auth/login')
def hash_password(p): return pwd.hash(p)
def verify_password(p,h): return pwd.verify(p,h)
def create_token(user):
    return jwt.encode({'sub':str(user.id),'role':user.role,'exp':datetime.utcnow()+timedelta(minutes=EXPIRE)},SECRET_KEY,algorithm=ALGORITHM)
def current_user(token:str=Depends(oauth2), db:Session=Depends(get_db)):
    exc=HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail='Invalid authentication',headers={'WWW-Authenticate':'Bearer'})
    try: data=jwt.decode(token,SECRET_KEY,algorithms=[ALGORITHM]); uid=int(data['sub'])
    except (JWTError,KeyError,ValueError): raise exc
    user=db.get(User,uid)
    if not user: raise exc
    return user
def require_roles(*roles):
    def dep(user=Depends(current_user)):
        if user.role not in roles: raise HTTPException(403,'Insufficient permissions')
        return user
    return dep
