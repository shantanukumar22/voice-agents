{
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
          "description": "Additional notes, observations, or clinical correlations from the lab"
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
            "description": "Type of scan performed (e.g., X-Ray, MRI, CT Scan, Ultrasound, PET Scan, DEXA, Mammography, Angiography, Echocardiogram)"
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
        }
      }
    }
  },
  "DATA_SOURCE_TYPES": {
    "OCR": {
      "type": "ocr",
      "description": "Data extracted from scanned medical documents via OCR",
      "content": {
        "type": "object",
        "properties": {
          "text": {
            "type": "string",
            "required": false,
            "description": "OCR extracted text from the document"
          },
          "image": {
            "type": "string",
            "required": false,
            "description": "File path or reference to the scanned document image"
          }
        }
      },
      "metadata": {
        "createdAt": {
          "type": "string",
          "format": "ISO_8601",
          "required": true,
          "description": "Timestamp when OCR extraction was performed"
        },
        "ocr_confidence": {
          "type": "number",
          "required": false,
          "description": "OCR confidence score (0-100)"
        },
        "source_file_name": {
          "type": "string",
          "required": false,
          "description": "Original file name of the scanned document"
        }
      }
    },
    "DOCTOR_CONSULT": {
      "type": "doctor_consult",
      "description": "Real-time consultation data entered by doctor through text input or image attachment",
      "content": {
        "type": "object",
        "properties": {
          "text": {
            "type": "string",
            "required": false,
            "description": "Doctor's consultation notes, observations, and recommendations in text format"
          },
          "image": {
            "type": "string",
            "required": false,
            "description": "File path or reference to images/attachments provided by doctor (e.g., handwritten notes, diagnostic images, sketches)"
          }
        }
      },
      "metadata": {
        "createdAt": {
          "type": "string",
          "format": "ISO_8601",
          "required": true,
          "description": "Timestamp when doctor entered the consultation data"
        },
        "doctor_name": {
          "type": "string",
          "required": false,
          "description": "Name of the consulting doctor"
        },
        "doctor_id": {
          "type": "string",
          "required": false,
          "description": "Unique identifier for the doctor"
        },
        "specialization": {
          "type": "string",
          "required": false,
          "description": "Doctor's medical specialization"
        }
      }
    },
    "PATIENT_OPINION": {
      "type": "patient_opinion",
      "description": "Patient's self-reported information, symptoms, and feedback provided through text or image input",
      "content": {
        "type": "object",
        "properties": {
          "text": {
            "type": "string",
            "required": false,
            "description": "Patient's description of symptoms, concerns, medical history, or feedback in text format"
          },
          "image": {
            "type": "string",
            "required": false,
            "description": "File path or reference to images/attachments provided by patient (e.g., body parts showing symptoms, test reports, medication bottles)"
          }
        }
      },
      "metadata": {
        "createdAt": {
          "type": "string",
          "format": "ISO_8601",
          "required": true,
          "description": "Timestamp when patient provided the information"
        },
        "patient_id": {
          "type": "string",
          "required": false,
          "description": "Unique identifier for the patient"
        },
        "patient_name": {
          "type": "string",
          "required": false,
          "description": "Patient's name"
        }
      }
    }
  },
  "OUTPUT_FORMAT": {
    "structured_document": {
      "document_id": {
        "type": "string",
        "description": "Auto-generated UUID for the document"
      },
      "document_type": {
        "type": "string",
        "description": "Type of medical document (PRESCRIPTION, LABORATORY_REPORT, DISCHARGE_SUMMARY, IMAGING_REPORT)"
      },
      "extraction_timestamp": {
        "type": "string",
        "format": "ISO_8601",
        "description": "Timestamp when the document was processed"
      },
      "confidence_score": {
        "type": "number",
        "minimum": 0,
        "maximum": 100,
        "description": "Overall extraction confidence score"
      },
      "data_sources": {
        "type": "array",
        "description": "Array of data sources contributing to this document",
        "items": {
          "type": "object",
          "properties": {
            "source_id": {
              "type": "string",
              "description": "Unique identifier for the data source instance"
            },
            "source_type": {
              "type": "string",
              "enum": ["OCR", "DOCTOR_CONSULT", "PATIENT_OPINION"],
              "description": "Type of data source"
            },
            "content": {
              "type": "object",
              "properties": {
                "text": {
                  "type": "string",
                  "description": "Textual content from the source"
                },
                "image": {
                  "type": "string",
                  "description": "File reference for any images/attachments"
                }
              }
            },
            "metadata": {
              "type": "object",
              "description": "Source-specific metadata (see DATA_SOURCE_TYPES)"
            },
            "processed": {
              "type": "boolean",
              "description": "Whether this data source has been processed and integrated"
            }
          },
          "required": ["source_id", "source_type", "content", "metadata"]
        }
      },
      "extracted_data": {
        "type": "object",
        "description": "Extracted and structured data according to DOCUMENT_TYPES schema"
      },
      "extraction_errors": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "field": {
              "type": "string",
              "description": "Field name where error occurred"
            },
            "error": {
              "type": "string",
              "description": "Error description"
            },
            "severity": {
              "type": "string",
              "enum": ["critical", "warning", "info"],
              "description": "Error severity level"
            },
            "source_id": {
              "type": "string",
              "description": "Data source where the error originated"
            }
          }
        }
      }
    }
  },
  "EXAMPLE_RESPONSE": {
    "document_id": "550e8400-e29b-41d4-a716-446655440000",
    "document_type": "PRESCRIPTION",
    "extraction_timestamp": "2024-01-15T10:30:00Z",
    "confidence_score": 92,
    "data_sources": [
      {
        "source_id": "ocr_001",
        "source_type": "OCR",
        "content": {
          "text": "Amoxicillin 500mg twice daily for 7 days...",
          "image": "/uploads/prescription_scan_001.jpg"
        },
        "metadata": {
          "createdAt": "2024-01-15T09:15:00Z",
          "ocr_confidence": 95,
          "source_file_name": "prescription_001.jpg"
        },
        "processed": true
      },
      {
        "source_id": "doctor_consult_001",
        "source_type": "DOCTOR_CONSULT",
        "content": {
          "text": "Patient showing signs of bacterial infection. Prescribed antibiotics. Monitor for allergic reactions. Follow-up in 1 week.",
          "image": "/uploads/doctor_notes_sketch_001.jpg"
        },
        "metadata": {
          "createdAt": "2024-01-15T09:45:00Z",
          "doctor_name": "Dr. Rajesh Kumar",
          "doctor_id": "DOC_12345",
          "specialization": "General Medicine"
        },
        "processed": true
      },
      {
        "source_id": "patient_opinion_001",
        "source_type": "PATIENT_OPINION",
        "content": {
          "text": "I have had a persistent cough for 3 days with fever. Started yesterday evening at 38.5°C. No other symptoms.",
          "image": "/uploads/patient_symptom_photo_001.jpg"
        },
        "metadata": {
          "createdAt": "2024-01-15T09:00:00Z",
          "patient_id": "PAT_98765",
          "patient_name": "John Doe"
        },
        "processed": true
      }
    ],
    "extracted_data": {
      "metadata": {
        "document_date": "2024-01-15",
        "prescribing_doctor": "Dr. Rajesh Kumar",
        "hospital_clinic_name": "City Medical Center"
      },
      "patient_info": {
        "age": "35",
        "gender": "M"
      },
      "diagnosis": [
        {
          "diagnosis_name": "Bacterial respiratory infection",
          "severity": "Moderate"
        }
      ],
      "medications": [
        {
          "medication_name": "Amoxicillin",
          "dosage": "500mg",
          "frequency": "Twice daily",
          "duration": "7 days",
          "route": "oral",
          "special_instructions": "With food"
        }
      ]
    },
    "extraction_errors": [
      {
        "field": "hospital_clinic_name",
        "error": "Could not extract from OCR. Inferred from doctor consultation notes.",
        "severity": "warning",
        "source_id": "ocr_001"
      }
    ]
  }
}