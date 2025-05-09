

import ceas.config as cfg

import pandas as pd
dfs = pd.read_pickle(cfg.INTERIM_DATA_DIR/"dfs.pkl")

df_applicants = dfs['applicants'].copy()
df_requests = dfs['requests'].copy()
request = pd.read_pickle(cfg.PROJ_ROOT/"request.pickle")

def filter_applicants_by_request(new_request, df_applicants):
    """
    Given a new request dictionary (as validated above) and a DataFrame 'df_applicants'
    that contains the 'applicants' table or an equivalent derived table with available candidates,
    apply the relevant filters to return a subset that matches the request's criteria.

    Typical filters:
      - Genero if != "Indiferente"
      - For each 'nivel_educativo', we might check the applicant's ed_licence_level
      - For each 'asignatura' needed, we might check applicant's 'subjects'
      - If date range implies certain days (and request demands "Completa" availability),
        we only want applicants whose available_days covers all those days

    Adjust or expand the logic as needed. This is a general skeleton.
    """
    subset = df_applicants.copy()
    print("request", new_request)

    # 1. Genero filter (if request['genero'] != "Indiferente")
    genero_req = new_request.get("genero", "Indiferente")
    if genero_req != "Indiferente":
        subset = subset[ subset["genero"] == genero_req ]

    # 2. ed_licence_level filter
    # request has e.g. new_request["nivel_educativo"] = ["Media","Básica",...]
    #nivel_req = new_request.get("nivel_educativo", [])
    cursos_req = new_request.get("curso", {})
    print("cursos_req", cursos_req)
    # curso tiene el formato {nivel_educativo: [cursos]}
    # e.g. {"Media": ["1° Medio", "2° Medio"], "Básica": ["3° Básico", "4° Básico"]}

    # entonces, 

    
    print("ed_licence_level", subset["ed_licence_level"].unique())
    if nivel_req:
        # check if applicant's ed_licence_level has at least one of the requested
        subset = subset[
            subset["ed_licence_level"].apply(
                lambda app_levels: any(niv in app_levels for niv in nivel_req)
            )
        ]

    # 3. asignaturas
    # new_request["asignatura"] = {nivel -> list}, or list
    # We'll do a simplified approach: flatten all assigned subjects
    requested_subjs = []
    asig_val = new_request.get("asignatura", {})
    if isinstance(asig_val, dict):
        for k,arr in asig_val.items():
            requested_subjs.extend(arr)
    elif isinstance(asig_val, list):
        requested_subjs = asig_val
    requested_subjs = list(set(requested_subjs))  # unique

    if requested_subjs:
        # filter where applicant's "subjects" intersects with requested_subjs
        subset = subset[
            subset["subjects"].apply(
                lambda s: any(subj in s for subj in requested_subjs)
            )
        ]

    # 4. Disponibilidad
    # If "Completa" => applicant must have all days in new_request["dias_seleccionados"].
    # If "Parcial" => at least one day in common.
    disp_type = new_request.get("disponibilidad", "Parcial")  # default "Parcial"?
    req_days = new_request.get("dias_seleccionados", [])
    if req_days:
        if disp_type == "Completa":
            # only those applicants whose available_days contains all req_days
            subset = subset[
                subset["available_days"].apply(
                    lambda app_days: all(day in app_days for day in req_days)
                )
            ]
        else:
            # "Parcial" => intersection not empty
            subset = subset[
                subset["available_days"].apply(
                    lambda app_days: any(day in app_days for day in req_days)
                )
            ]

    # 5. anios_egreso => e.g. 'undergrad_year' is a DATETIME => check difference from current date
    # if we assume "anios_egreso" means minimum years since they graduated
    anios_min = new_request.get("anios_egreso", 0)
    if anios_min > 0:
        import datetime
        now = datetime.datetime.now().date()
        def years_since(grad_date):
            # grad_date is e.g. an approx date in applicant's 'undergrad_year'
            if grad_date is None:
                return 0
            return now.year - grad_date.year
        subset = subset[
            subset["undergrad_year"].apply(lambda d: years_since(d) >= anios_min)
        ]

    # More filters can be appended as needed

    return subset

filter_applicants_by_request(request, df_applicants)
