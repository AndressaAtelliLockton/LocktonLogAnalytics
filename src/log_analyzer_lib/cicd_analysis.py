import pandas as pd
import re

def extract_cicd_metrics(df):
    """
    Extrai métricas de CI/CD e Processos de Background (Pipelines, Builds, Deploys, Tasks).
    Totalmente desacoplado com regex tolerantes e fallback para tarefas de sistema.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # 1. Busca ampla por termos de CI/CD, automação e tarefas agendadas/jobs
    keywords = r'pipeline|build|deploy|release|ci/cd|test|github|gitlab|jenkins|sonar|argo|octopus|ansible|bitbucket|task|job|batch|runner|action|step|stage|execution|webhook|process'
    
    mask = df['message'].astype(str).str.contains(keywords, case=False, regex=True)
    if 'source' in df.columns:
        mask |= df['source'].astype(str).str.contains(keywords, case=False, regex=True)
    if 'category' in df.columns:
        mask |= df['category'].astype(str).str.contains(r'ci/cd|pipeline|deploy|job|task', case=False, regex=True)
    if 'tag' in df.columns:
        mask |= df['tag'].astype(str).str.contains(keywords, case=False, regex=True)
        
    cicd_df = df[mask].copy()
    
    # 2. FALLBACK AGRESSIVO: Se não achar termos clássicos de CI/CD, busca por logs de processamento com duração
    # Isso garante que a página sempre mostre dados úteis sobre tarefas longas do sistema
    if cicd_df.empty:
        fallback_mask = df['message'].astype(str).str.contains(r'duration|elapsed|took|execution', case=False, regex=True)
        cicd_df = df[fallback_mask].copy()

    if cicd_df.empty:
        return pd.DataFrame()

    msg_series = cicd_df['message'].astype(str)

    # 3. Extração de Status (Tolerante)
    cicd_df['status'] = 'Unknown'
    cicd_df.loc[msg_series.str.contains(r'success|pass|completed|succeeded|ok|200|done', case=False, regex=True), 'status'] = 'Success'
    cicd_df.loc[msg_series.str.contains(r'fail|error|broken|exception|timeout|404|500', case=False, regex=True), 'status'] = 'Failure'
    cicd_df.loc[msg_series.str.contains(r'start|running|progress|pending|init', case=False, regex=True), 'status'] = 'In Progress'

    # 4. Extração de Duração (Regex atualizada para suportar JSON, aspas, espaços e variações)
    dur_pattern = r'(?:duration|took|time|elapsed(?:milliseconds)?|in|after)(?:["\']?[:=]\s*["\']?|\s+["\']?)(\d+(?:\.\d+)?)(?:["\']|\s+)?(ms|s|sec|m|min|us|µs)?'
    dur_extract = msg_series.str.extract(dur_pattern, flags=re.IGNORECASE)
    
    cicd_df['duration_s'] = 0.0
    
    if not dur_extract.empty and dur_extract.shape[1] == 2:
        vals = pd.to_numeric(dur_extract[0], errors='coerce').fillna(0)
        units = dur_extract[1].str.lower().fillna('ms') # Assume milissegundos como padrão
        
        s_mask = units.isin(['s', 'sec'])
        ms_mask = units.isin(['ms', 'us', 'µs'])
        m_mask = units.isin(['m', 'min'])
        
        cicd_df.loc[s_mask, 'duration_s'] = vals[s_mask]
        cicd_df.loc[ms_mask, 'duration_s'] = vals[ms_mask] / 1000.0
        cicd_df.loc[m_mask, 'duration_s'] = vals[m_mask] * 60.0

    # 5. Identificação do Estágio (Stage)
    cicd_df['stage'] = 'Process/Task'
    cicd_df.loc[msg_series.str.contains('build|compile|assemble', case=False, regex=True), 'stage'] = 'Build'
    cicd_df.loc[msg_series.str.contains('test|check|verify|lint|sonar', case=False, regex=True), 'stage'] = 'Test'
    cicd_df.loc[msg_series.str.contains('deploy|release|publish|push', case=False, regex=True), 'stage'] = 'Deploy'
    cicd_df.loc[msg_series.str.contains('db|database|sql|query|migration', case=False, regex=True), 'stage'] = 'Database Job'

    return cicd_df