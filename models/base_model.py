from utils.db import db

class BaseModel(db.Model):
    def to_dict(self):
        return { 
            c.name: getattr(self, c.name) for c in self.__table__.columns 
        }
        
