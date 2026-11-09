from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from typing import List, Optional

# 1. إعداد قاعدة البيانات (SQLite)
DATABASE_URL = "sqlite:///./medical_records.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. نماذج قاعدة البيانات (SQLAlchemy Models)
class PatientModel(Base):
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    medical_id = Column(String, unique=True, index=True) # الرقم الطبي الموحد
    name = Column(String, index=True)
    phone = Column(String, index=True)
    birth_date = Column(String)
    blood_type = Column(String)
    
    # علاقة المريض بسجلاته الطبية
    records = relationship("MedicalRecordModel", back_populates="patient")

class MedicalRecordModel(Base):
    __tablename__ = "medical_records"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    visit_date = Column(String)
    diagnosis = Column(Text) # التشخيص
    treatment = Column(Text) # العلاج والأدوية
    notes = Column(Text)
    
    patient = relationship("PatientModel", back_populates="records")

# إنشاء الجداول في قاعدة البيانات
Base.metadata.create_all(bind=engine)

# 3. نماذج البيانات للمدخلات والمخرجات (Pydantic Schemas)
class MedicalRecordCreate(BaseModel):
    visit_date: str
    diagnosis: str
    treatment: str
    notes: Optional[str] = None

class MedicalRecordResponse(MedicalRecordCreate):
    id: int
    class Config:
        from_attributes = True

class PatientCreate(BaseModel):
    medical_id: str
    name: str
    phone: str
    birth_date: str
    blood_type: str

class PatientResponse(PatientCreate):
    id: int
    records: List[MedicalRecordResponse] = []
    class Config:
        from_attributes = True

# 4. إعداد تطبيق FastAPI
app = FastAPI(title="نظام إدارة السجلات الطبية والأرشيف")

# دالة للحصول على جلسة اتصال بقاعدة البيانات
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 5. الواجهات البرمجية (API Endpoints)

# أ) إضافة مريض جديد
@app.post("/patients/", response_model=PatientResponse)
def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    db_patient = db.query(PatientModel).filter(PatientModel.medical_id == patient.medical_id).first()
    if db_patient:
        raise HTTPException(status_code=400, detail="الرقم الطبي مسجل مسبقاً لمريض آخر")
    
    new_patient = PatientModel(**patient.dict())
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)
    return new_patient

# ب) إضافة سجل طبي / زيارة لمريض
@app.post("/patients/{patient_id}/records/", response_model=MedicalRecordResponse)
def add_medical_record(patient_id: int, record: MedicalRecordCreate, db: Session = Depends(get_db)):
    patient = db.query(PatientModel).filter(PatientModel.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="المريض غير موجود")
    
    new_record = MedicalRecordModel(**record.dict(), patient_id=patient_id)
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return new_record

# ج) البحث المتقدم عن المرضى
@app.get("/patients/search/", response_model=List[PatientResponse])
def search_patients(query: str, db: Session = Depends(get_db)):
    # البحث المارن بواسطة الاسم، الهاتف، أو الرقم الطبي
    results = db.query(PatientModel).filter(
        or_(
            PatientModel.name.contains(query),
            PatientModel.phone.contains(query),
            PatientModel.medical_id == query
        )
    ).all()
    return results
