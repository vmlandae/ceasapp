# create_fake_data.py
# 
# SCRIPT PARA GENERAR DATOS FICTICIOS PARA EL SISTEMA DE REEMPLAZOS CORTOS
# Corregido para asegurar que haya un mínimo de replacements con estado "realizado"/"cerrado"
# y así evitar el ValueError de muestreo.
#
# Además, revisa la coherencia general de referencias (applicants -> candidates, etc.)

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from ceas import config as cfg
def generate_fictitious_data():
    # 1) SCHOOLS (12 registros: 1 Oficina Central + 11 Colegios)
    schools_data = []
    # Oficina Central
    schools_data.append({
        "school_id": 1,
        "school_name": "Oficina Central",
        "address": "Calle Central 100",
        "comuna": "Santiago",
        "status": "activo",
        "type": "oficina_central"
    })
    # 11 colegios
    for i in range(2, 13):
        schools_data.append({
            "school_id": i,
            "school_name": f"Colegio_{i-1}",
            "address": f"Calle Ficticia {i*10}",
            "comuna": np.random.choice(["Santiago","Providencia","Maipu","Puente Alto"]),
            "status": "activo",
            "type": "colegio"
        })
    df_schools = pd.DataFrame(schools_data)

    # 2) USERS (~20 usuarios)
    roles = ["owner", "admin", "oficina_central","admin_colegio","user_colegio"]
    users_data = []
    user_id_counter = 1

    # 1 "owner"
    users_data.append({
        "user_id": user_id_counter,
        "email": "owner@ceas.cl",
        "name": "Owner CEAS",
        "role": "owner",
        "school_id": 1,
        "status": "activo",
        "created_at": datetime(2023,1,1),
        "last_login": datetime(2023,1,2)
    })
    user_id_counter += 1

    # 1 "admin"
    users_data.append({
        "user_id": user_id_counter,
        "email": "admin@ceas.cl",
        "name": "Admin CEAS",
        "role": "admin",
        "school_id": 1,
        "status": "activo",
        "created_at": datetime(2023,1,1),
        "last_login": datetime(2023,1,5)
    })
    user_id_counter += 1

    # 2 "oficina_central"
    for i in range(2):
        users_data.append({
            "user_id": user_id_counter,
            "email": f"central_{i}@ceas.cl",
            "name": f"CentralUser_{i}",
            "role": "oficina_central",
            "school_id": 1,
            "status": "activo",
            "created_at": datetime(2023,1,10) + timedelta(days=i),
            "last_login": datetime(2023,1,12) + timedelta(days=i)
        })
        user_id_counter += 1

    # ~16 usuarios para colegios
    for i in range(16):
        role = np.random.choice(["admin_colegio","user_colegio"])
        school_id = np.random.randint(2,13)  # uno de los 11 colegios
        users_data.append({
            "user_id": user_id_counter,
            "email": f"user_{school_id}_{i}@colegio.cl",
            "name": f"User_{school_id}_{i}",
            "role": role,
            "school_id": school_id,
            "status": "activo",
            "created_at": datetime(2023,1,1) + timedelta(days=np.random.randint(0,15)),
            "last_login": datetime(2023,1,20) + timedelta(days=np.random.randint(0,5))
        })
        user_id_counter += 1

    df_users = pd.DataFrame(users_data)

    # 3) APPLICANTS (~100)
    applicants_data = []
    applicant_id_counter = 1

    possible_genders = ["Masculino","Femenino","Otro"]
    possible_days = ["Lunes","Martes","Miércoles","Jueves","Viernes"]
    possible_subjects = [
        "Artes Visuales","Artes Musicales","Biología","Ciencias Naturales","Educación Física y Salud",
        "Filosofía","Física (CN)","Historia, geografía y Ciencias Sociales","Inglés","Lenguaje y Comunicación",
        "Matemática","Orientación","Química","Religión","Tecnología","TP - Mecánica Automotriz",
        "TP - Electricidad","TP - Contabilidad","Otros"
    ]
    possible_ed_levels = [
        "Educación Media [7° a IV medio]",
        "Educación Básica con mención [1° a 6° Básico]",
        "Educación Técnico Profesional",
        "Educación Parvularia [Kínder y Pre kínder]",
        "Educación Diferencial"
    ]
    possible_universities = [
        "U. de Chile","U. de Santiago De Chile","Pontificia U. Católica De Chile","U. de Concepción",
        "IP Inacap","U. Mayor","U. Adolfo Ibañez","U. Austral De Chile","Otra"
    ]

    for i in range(100):
        num_subjs = np.random.randint(1,4)
        chosen_subjs = np.random.choice(possible_subjects, size=num_subjs, replace=False)
        num_eds = np.random.randint(1,3)
        chosen_eds = np.random.choice(possible_ed_levels, size=num_eds, replace=False)
        num_days = np.random.randint(1,6)
        chosen_days = np.random.choice(possible_days, size=num_days, replace=False)

        applicants_data.append({
            "applicant_id": applicant_id_counter,
            "timestamp": datetime(2023,1,1,9,0) + timedelta(days=np.random.randint(0,30), minutes=i),
            "email": f"appl_{i}@mail.com",
            "first_name": f"Name_{i}",
            "last_name": f"Last_{i}",
            "second_last_name": f"Second_{i}",
            "rut": f"{np.random.randint(1000000,25000000)}",
            "phone": f"+569{np.random.randint(10000000,99999999)}",
            "comuna_residencia": np.random.choice(["Santiago","Providencia","Puente Alto","Macul"]),
            "genero": np.random.choice(possible_genders),
            "ed_licence_level": list(chosen_eds),
            "subjects": list(chosen_subjs),
            "university": np.random.choice(possible_universities),
            "undergrad_year": datetime(2022,6,10) - timedelta(days=np.random.randint(0,3000)),
            "available_days": list(chosen_days),
            "max_hours_per_week": np.random.randint(5,45),
            "complementary_information": f"Info extra {i}",
            "cv_link": f"https://drive.google.com/fake_cv_link_{i}",
            "qualified_to_work_at_schools_cert": f"https://drive.google.com/fake_cert_link_{i}"
        })
        applicant_id_counter += 1

    df_applicants = pd.DataFrame(applicants_data)

    # 4) CANDIDATES (~15) a partir de APPLICANTS
    candidates_data = []
    candidate_id_counter = 1
    chosen_applicants = np.random.choice(df_applicants["applicant_id"], size=15, replace=False)
    possible_validation_status = ["sin_procesar","validado","rechazado"]

    # Obtenemos un subset de users que puedan "validar" (admin u oficina_central)
    validators = df_users[df_users["role"].isin(["admin","oficina_central"])]
    if validators.empty:
        # Garantizar que existe al menos un validador
        # Forzamos que el user_id=2 (el admin que creamos) sea un validador
        validators = pd.DataFrame([df_users.iloc[1]])

    for app_id in chosen_applicants:
        val_status = np.random.choice(possible_validation_status)
        validated_by = None
        validated_at = None
        if val_status in ["validado","rechazado"]:
            validated_by = int(validators.sample(1)["user_id"].iloc[0])
            validated_at = datetime(2023,2,1) + timedelta(days=np.random.randint(0,15))

        validated_phone = None
        whatsapp = False
        if val_status == "validado":
            validated_phone = f"+569{np.random.randint(10000000,99999999)}"
            whatsapp = bool(np.random.randint(0,2))

        candidates_data.append({
            "candidate_id": candidate_id_counter,
            "applicant_id": app_id,
            "validation_status": val_status,
            "validated_at": validated_at,
            "validated_by": validated_by,
            "verified_email": f"valid_{app_id}@ceas.cl" if val_status=="validado" else None,
            "validated_phone": validated_phone,
            "whatsapp": whatsapp,
            "validated_rut": f"{np.random.randint(1000000,25000000)}-{np.random.randint(0,10)}" if val_status=="validado" else None,
            "names": f"Candidate_{candidate_id_counter}",
            "last_names": "LastNames"
        })
        candidate_id_counter += 1

    df_candidates = pd.DataFrame(candidates_data)

    # 5) REPLACEMENTS (~8)
    replacements_data = []
    replacement_id_counter = 1

    # Seleccionamos usuarios que sean admin_colegio o user_colegio
    possible_college_users = df_users[df_users["role"].isin(["admin_colegio","user_colegio"])]
    # Creamos 8 replacements con la salvedad de obligar al menos 4 a ser "realizado" o "cerrado"
    forced_done = 4  # Queremos 4 con "realizado" o "cerrado"
    for i in range(8):
        user_sel = possible_college_users.sample(1).iloc[0]
        created_at = datetime(2023,2,1) + timedelta(days=np.random.randint(0,10))
        start_dt = created_at + timedelta(days=np.random.randint(1,5))
        end_dt = start_dt + timedelta(days=np.random.randint(3,7))

        # Asignamos status
        if i < forced_done:
            # Forzamos que al menos 4 tengan estado "realizado" o "cerrado"
            st_list = ["realizado","cerrado"]
        else:
            st_list = ["creada","pendiente validación","selección candidatos","eleccion candidato","realizado","cerrado"]
        st_choice = np.random.choice(st_list)

        replacements_data.append({
            "replacement_id": replacement_id_counter,
            "school_id": int(user_sel["school_id"]),
            "created_by": int(user_sel["user_id"]),
            "title": f"Reemplazo_{i}",
            "description": f"Descripcion del reemplazo {i}",
            "start_date": start_dt,
            "end_date": end_dt,
            "status": st_choice,
            "created_at": created_at,
            "updated_at": created_at + timedelta(days=np.random.randint(1,3))
        })
        replacement_id_counter += 1

    df_replacements = pd.DataFrame(replacements_data)

    # 6) REPLACEMENT_CANDIDATES
    # Asignar 2 candidatos por cada replacement
    replacement_candidates_data = []
    for rep_row in df_replacements.itertuples():
        # Random 2 candidates
        if len(df_candidates)==0:
            break
        cand_list = df_candidates.sample(min(2,len(df_candidates)))  # Evitar error si len < 2
        for _,cand_row in cand_list.iterrows():
            replacement_candidates_data.append({
                "replacement_id": rep_row.replacement_id,
                "candidate_id": cand_row["candidate_id"],
                "is_selected": bool(np.random.randint(0,2)),
                "contacted_at": rep_row.created_at + timedelta(days=np.random.randint(1,2)),
                "confirmation_status": np.random.choice(["disponible","no disponible","pendiente"])
            })
    df_replacement_candidates = pd.DataFrame(replacement_candidates_data)

    # 7) RECEPTIONS (~4) en replacements con estado "realizado" o "cerrado"
    receptions_data = []
    receptions_id_counter = 1

    done_mask = df_replacements["status"].isin(["realizado","cerrado"])
    repl_done = df_replacements[done_mask]
    if not repl_done.empty:
        sample_size = min(4, len(repl_done))
        repl_done_sample = repl_done.sample(n=sample_size, replace=False)
        for rep in repl_done_sample.itertuples():
            # choose any candidate from replacement_candidates
            rcands = df_replacement_candidates[df_replacement_candidates["replacement_id"]==rep.replacement_id]
            if not rcands.empty:
                chosen_cand = rcands.sample(1).iloc[0]
                rec_dt = rep.end_date + timedelta(days=1)
                receptions_data.append({
                    "reception_id": receptions_id_counter,
                    "replacement_id": rep.replacement_id,
                    "candidate_id": chosen_cand["candidate_id"],
                    "receipt_date": rec_dt,
                    "rating": np.random.randint(1,6),
                    "observations": f"Observaciones Reemplazo {rep.replacement_id}"
                })
                receptions_id_counter += 1

    df_receptions = pd.DataFrame(receptions_data)

    # Retorna dataframes en el formato "appReemplazosXxx"
    return {
        "appSchools": df_schools,
        "appUsers": df_users,
        "appApplicants": df_applicants,
        "appCandidates": df_candidates,
        "appReplacements": df_replacements,
        "appCandidates": df_replacement_candidates,
        "appReceptions": df_receptions
    }

if __name__ == "__main__":
    
    dataframes = generate_fictitious_data()
    # vamos a guardar los dataframes en un archivo xlsx llamado fake_data_reemplazos.xlsx en el path cfg.INTERIM_DATA_DIR / "fake_data_reemplazos.xlsx" para luego subirlos a Google Sheets

    with pd.ExcelWriter(cfg.INTERIM_DATA_DIR / "fake_data_reemplazos.xlsx") as writer:
        for key, df in dataframes.items():
            df.to_excel(writer, sheet_name=key, index=False)
    print("Dataframes guardados en fake_data_reemplazos.xlsx")