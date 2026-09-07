{
  "OCR_SCHEMA": {
    "version": "1.0",
    "description": "Schema for extracting and structuring clinical data from medical documents via OCR",
    
    "DOCUMENT_TYPES": {
      "PRESCRIPTION": {
        "document_type": "prescription",
        "fields": {
          "metadata": {
            "document_date": {
              "type": "date",
              "format": "YYYY-MM-DD",
              "required": true,
              "description": "Date of prescription issuance"
            },
            "prescribing_doctor": {
              "type": "string",
              "required": false,
              "description": "Doctor's name who prescribed"
            },
            "hospital_clinic_name": {
              "type": "string",
              "required": false,
              "description": "Healthcare facility name"
            },
            "contact_details": {
              "type": "string",
              "required": false,
              "description": "Hospital/clinic contact info"
            }
          },
          "patient_info": {
            "age": {
              "type": "string",
              "required": true,
              "description": "Patient's age at time of prescription"
            },
            "gender": {
              "type": "string",
              "required": false,
              "enum": ["M", "F", "O"]
            }
          },
          "vital_signs": {
            "blood_pressure": {
              "type": "string",
              "required": false,
              "example": "120/80 mmHg",
              "description": "Systolic/Diastolic in mmHg"
            },
            "temperature": {
              "type": "string",
              "required": false,
              "example": "98.6°F or 37°C",
              "description": "Body temperature"
            },
            "pulse_rate": {
              "type": "string",
              "required": false,
              "example": "72 bpm",
              "description": "Heart rate in beats per minute"
            },
            "respiratory_rate": {
              "type": "string",
              "required": false,
              "example": "16 breaths/min",
              "description": "Breathing rate"
            },
            "oxygen_saturation": {
              "type": "string",
              "required": false,
              "example": "98% SpO2",
              "description": "Blood oxygen saturation"
            },
            "weight": {
              "type": "string",
              "required": false,
              "example": "70 kg",
              "description": "Patient weight"
            },
            "height": {
              "type": "string",
              "required": false,
              "example": "175 cm",
              "description": "Patient height"
            },
            "bmi": {
              "type": "string",
              "required": false,
              "example": "22.8",
              "description": "Body Mass Index"
            }
          },
          "diagnosis": {
            "type": "array",
            "required": true,
            "description": "Doctor's clinical assessment and diagnoses",
            "items": {
              "diagnosis_name": {
                "type": "string",
                "required": true,
                "description": "Primary or secondary diagnosis"
              },
              "severity": {
                "type": "string",
                "required": false,
                "enum": ["Acute", "Chronic", "Mild", "Moderate", "Severe"]
              }
            }
          },
          "clinical_notes": {
            "type": "string",
            "required": false,
            "description": "Any additional clinical observations by doctor"
          },
          "medications": {
            "type": "array",
            "required": true,
            "description": "Medications prescribed based on diagnosis",
            "items": {
              "medication_name": {
                "type": "string",
                "required": true
              },
              "dosage": {
                "type": "string",
                "required": true,
                "example": "500mg, 10ml, 1 tablet"
              },
              "frequency": {
                "type": "string",
                "required": true,
                "example": "Once daily, Twice daily, TDS, BD, HS"
              },
              "duration": {
                "type": "string",
                "required": false,
                "example": "7 days, 2 weeks, 1 month"
              },
              "route": {
                "type": "string",
                "required": false,
                "enum": ["oral", "injection", "topical", "inhalation", "rectal", "sublingual"]
              },
              "special_instructions": {
                "type": "string",
                "required": false,
                "example": "After food, Empty stomach, With water"
              }
            }
          },
          "other_info": {
            "type": "string",
            "required": false,
            "description": "Any additional information or special notes from prescription (diet restrictions, precautions, lifestyle modifications, etc.)"
          },
          "image_file": {
            "type": "string",
            "required": false,
            "description": "Path or reference to the scanned prescription file (image, PDF, or digital file)"
          }
        }
      },

      "LABORATORY_REPORT": {
        "document_type": "laboratory_report",
        "fields": {
          "metadata": {
            "referred_by": {
              "type": "string",
              "required": true,
              "description": "Name of the doctor/physician who referred the patient for tests"
            },
            "sample_collection_date": {
              "type": "date",
              "format": "YYYY-MM-DD",
              "required": true,
              "description": "Date when samples were collected"
            },
            "sample_collected_by": {
              "type": "string",
              "required": false,
              "description": "Name of technician/phlebotomist who collected the sample"
            },
            "report_date": {
              "type": "date",
              "format": "YYYY-MM-DD",
              "required": true,
              "description": "Date when report was generated"
            },
            "report_generated_by": {
              "type": "string",
              "required": false,
              "description": "Name of pathologist/technician who generated the report"
            },
            "lab_name": {
              "type": "string",
              "required": false,
              "description": "Laboratory name"
            },
            "lab_id": {
              "type": "string",
              "required": false,
              "description": "Lab reference/accreditation ID"
            },
            "test_ordered_by": {
              "type": "string",
              "required": false,
              "description": "Consulting physician name (may differ from referred_by)"
            }
          },
          "patient_info": {
            "patient_id": {
              "type": "string",
              "required": false
            },
            "age": {
              "type": "string",
              "required": false
            },
            "gender": {
              "type": "string",
              "required": false,
              "enum": ["M", "F", "O"]
            }
          },
          "test_results": {
            "type": "array",
            "required": true,
            "items": {
              "test_name": {
                "type": "string",
                "required": true,
                "example": "Hemoglobin, Glucose, Creatinine"
              },
              "test_value": {
                "type": "string",
                "required": true,
                "example": "13.5"
              },
              "unit": {
                "type": "string",
                "required": true,
                "example": "g/dL, mg/dL, mg/L"
              },
              "reference_range": {
                "type": "string",
                "required": false,
                "example": "12-16 g/dL"
              },
              "reference_min": {
                "type": "number",
                "required": false
              },
              "reference_max": {
                "type": "number",
                "required": false
              },
              "status": {
                "type": "string",
                "required": false,
                "enum": ["Normal", "High", "Low", "Critical"]
              },
              "abnormal_flag": {
                "type": "boolean",
                "required": true,
                "description": "True if value is out of range"
              }
            }
          },
          "remarks": {
            "type": "string",
            "required": false,
            "description": "Lab technician or doctor remarks"
          },
          "extra_notes": {
            "type": "string",
            "required": false,
            "description": "Additional notes, observations, or clinical correlations from the lab (e.g., sample quality, special handling, recommendations for follow-up)"
          },
          "image_file": {
            "type": "string",
            "required": false,
            "description": "Path or reference to the scanned lab report file (image, PDF, or digital file)"
          }
        }
      },

      "DISCHARGE_SUMMARY": {
        "document_type": "discharge_summary",
        "fields": {
          "metadata": {
            "admission_date": {
              "type": "date",
              "format": "YYYY-MM-DD",
              "required": true
            },
            "discharge_date": {
              "type": "date",
              "format": "YYYY-MM-DD",
              "required": true
            },
            "hospital_name": {
              "type": "string",
              "required": true
            },
            "ward_department": {
              "type": "string",
              "required": false,
              "example": "Cardiology, Orthopedics, General Medicine"
            },
            "admission_against": {
              "type": "string",
              "required": false,
              "enum": ["Medical advice", "Own request", "Court orders"]
            }
          },
          "clinical_information": {
            "presenting_complaint": {
              "type": "string",
              "required": true,
              "description": "Chief complaint at admission"
            },
            "history_of_present_illness": {
              "type": "string",
              "required": false
            },
            "past_medical_history": {
              "type": "string",
              "required": false
            },
            "past_surgical_history": {
              "type": "string",
              "required": false
            },
            "allergies": {
              "type": "array",
              "required": false,
              "items": {
                "type": "string"
              }
            }
          },
          "diagnosis": {
            "type": "array",
            "required": true,
            "items": {
              "primary_diagnosis": {
                "type": "string",
                "required": true,
                "description": "Main diagnosis"
              },
              "icd_code": {
                "type": "string",
                "required": false,
                "description": "ICD-10 code if available"
              },
              "comorbidities": {
                "type": "array",
                "required": false,
                "items": {
                  "type": "string"
                }
              }
            }
          },
          "treatment_details": {
            "investigations_done": {
              "type": "array",
              "required": false,
              "items": {
                "type": "string"
              }
            },
            "procedures_performed": {
              "type": "array",
              "required": false,
              "items": {
                "procedure_name": {
                  "type": "string"
                },
                "procedure_date": {
                  "type": "date"
                }
              }
            },
            "treatment_summary": {
              "type": "string",
              "required": false,
              "description": "Summary of treatment provided"
            }
          },
          "discharge_medications": {
            "type": "array",
            "required": false,
            "items": {
              "medication_name": {
                "type": "string"
              },
              "dosage": {
                "type": "string"
              },
              "frequency": {
                "type": "string"
              },
              "duration": {
                "type": "string"
              }
            }
          },
          "discharge_advice": {
            "type": "string",
            "required": false,
            "description": "Patient discharge instructions"
          },
          "follow_up": {
            "type": "string",
            "required": false,
            "description": "Follow-up recommendations"
          },
          "treating_physician": {
            "type": "string",
            "required": false
          },
          "image_file": {
            "type": "string",
            "required": false,
            "description": "Path or reference to the scanned discharge summary file (image, PDF, or digital file)"
          }
        }
      },

      "IMAGING_REPORT": {
        "document_type": "imaging_report",
        "fields": {
          "metadata": {
            "scan_date": {
              "type": "date",
              "format": "YYYY-MM-DD",
              "required": true
            },
            "scan_type": {
              "type": "string",
              "required": true,
              "description": "Type of scan performed (e.g., X-Ray, MRI, CT Scan, Ultrasound, PET Scan, DEXA, Mammography, Angiography, Echocardiogram, or other imaging types)"
            },
            "body_part_scanned": {
              "type": "string",
              "required": true,
              "example": "Chest, Brain, Abdomen, Spine, Joint"
            },
            "imaging_center_name": {
              "type": "string",
              "required": false
            },
            "technician_name": {
              "type": "string",
              "required": false
            }
          },
          "patient_info": {
            "age": {
              "type": "string",
              "required": false
            },
            "gender": {
              "type": "string",
              "required": false,
              "enum": ["M", "F", "O"]
            }
          },
          "findings": {
            "clinical_indication": {
              "type": "string",
              "required": false,
              "description": "Reason for imaging"
            },
            "scan_findings": {
              "type": "string",
              "required": true,
              "description": "Detailed findings from scan"
            },
            "abnormalities_detected": {
              "type": "array",
              "required": false,
              "items": {
                "abnormality_name": {
                  "type": "string"
                },
                "location": {
                  "type": "string"
                },
                "severity": {
                  "type": "string",
                  "enum": ["Mild", "Moderate", "Severe"]
                }
              }
            }
          },
          "radiologist_impression": {
            "type": "string",
            "required": true,
            "description": "Radiologist's final interpretation"
          },
          "recommendations": {
            "type": "string",
            "required": false,
            "description": "Follow-up or additional tests recommended"
          },
          "radiologist_name": {
            "type": "string",
            "required": false
          },
          "image_file": {
            "type": "string",
            "required": false,
            "description": "Path or reference to the scanned imaging file (image, PDF, or digital file)"
          }
        }
      }
    },

    "OUTPUT_FORMAT": {
      "structured_document": {
        "document_id": "auto_generated_uuid",
        "document_type": "string",
        "extraction_timestamp": "ISO_8601",
        "confidence_score": "0-100",
        "data": "extracted_fields_as_per_type",
        "extraction_errors": [
          {
            "field": "field_name",
            "error": "error_description",
            "severity": "critical/warning/info"
          }
        ]
      }
    }
  }
}