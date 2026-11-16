# %% [markdown]
# # Circular Economy | Reproducible multiresolution nested Leiden optimizer
#
# **Input:** an existing `CE_Technology_Tree_Outputs/<run>/` directory **or**
# `all_outputs_bundle.zip` from the original run. This notebook **does not**
# repeat Lens retrieval, cleaning, n-gram extraction, or network formation.
#
# **Scientific safeguards:** fixed parameter grid; repeated seeded Leiden runs;
# resolution-neighborhood stability; separately audited feasibility gates;
# document-bootstrap perturbation on ROOT; complete per-node checkpoints;
# immutable source hashes; non-expert, evidence-based provisional labels.
#
# The primary discovery algorithm is **Leiden with RBConfiguration** throughout.
# The code does not substitute exploratory Louvain results for Leiden results.
#
# Edit the SETTINGS cell, run all cells. If Colab disconnects, run all again:
# the same network+configuration yields the same folder and replays checkpoints.

# %% [markdown]
# ## 1. Dependencies and fixed analysis plan

# %%
from __future__ import annotations
import sys, os, subprocess, importlib.util
NEEDED={'igraph':'python-igraph>=0.11','leidenalg':'leidenalg>=0.10',
        'pandas':'pandas>=2.1','numpy':'numpy>=1.26','scipy':'scipy>=1.11',
        'sklearn':'scikit-learn>=1.4','matplotlib':'matplotlib>=3.8',
        'openpyxl':'openpyxl>=3.1',
        'plotly':'plotly>=5.20','networkx':'networkx>=3.2'}
missing=[v for m,v in NEEDED.items() if importlib.util.find_spec(m) is None]
if missing:
    print('Installing ONLY missing packages:',missing)
    subprocess.check_call([sys.executable,'-m','pip','install','-q',*missing])

# %%
import io, json, math, time, hashlib, zipfile, platform, re, shutil, importlib.metadata, traceback, itertools
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict, deque
import numpy as np, pandas as pd
from scipy import sparse
from sklearn.metrics import adjusted_rand_score
import igraph as ig
import leidenalg as la
import matplotlib.pyplot as plt
import networkx as nx
import plotly.graph_objects as go

VERSION='2.1.0'
SETTINGS={
  # Set either path explicitly, or leave both blank for automatic discovery.
  'PROJECT_ROOT': os.environ.get('CE_PROJECT_ROOT',''),
  'PREVIOUS_RUN_DIR': '/content/drive/MyDrive/Academic/Circular Economy Taxonomy/CE_Technology_Tree_Outputs/c820f6a74c75_af0be36c5d76',  # explicitly reuse 42,410-record archived run
  'INPUT_BUNDLE_ZIP': '',  # .../all_outputs_bundle.zip
  'OPTIMIZER_FOLDER': 'CE_Leiden_Optimized_Taxonomy',
  'EXPECTED_LENS_ZIP_SHA_PREFIX':'c820f6a74c75', # old Lens source, verified against the 42,410-record run
  'EXPECTED_PREVIOUS_RUN_ID':'c820f6a74c75_af0be36c5d76',  # prevent accidental substitution of another run
  'EXPECTED_ANALYTICAL_PATENT_UNITS':42410,       # 42,410 units from the correct archived run
  # Predeclared, deliberately broad root resolution search; no ARI reduction.
  'ROOT_RESOLUTIONS': [0.10,0.15,0.20,0.25,0.30,0.35,0.50,0.70,1.00,1.30],
  # Children use a bounded local search relative to their selected parent gamma.
  'CHILD_GAMMA_MULTIPLIERS': [0.55,0.75,1.00,1.25,1.50],
  'MIN_GAMMA':0.035,'MAX_GAMMA':2.0,
  'ROOT_RESTARTS':6,'CHILD_RESTARTS':4,
  'SEED':20261113,
  'MAX_DEPTH':3,                       # ROOT depth 0; leaves up to depth 3
  'MAX_NODES':200,                     # computational safety, disclosed in audit
  'MIN_PARENT_TERMS':25,'MIN_CHILD_TERMS':8,'MIN_CHILD_PATENT_UNITS':10,
  'MIN_MODULARITY_IMPROVEMENT':0.025,
  'MIN_SEED_ARI':0.55,                 # heuristic, NOT '55% correctness'
  'MAX_CHILDREN_INCLUDING_RESIDUAL':15,
  'MAX_RESIDUAL_TERM_FRACTION':0.25,
  # Document resampling: ROOT candidates only, fixed original graph topology.
  'ROOT_BOOTSTRAP_CANDIDATES':0,     # 0 = audit and rank ALL feasible gamma values
  'ROOT_BOOTSTRAP_REPLICATES':4,
  # Bootstrap agreement is a RANKING CRITERION, not a new arbitrary pass/fail cutoff.
  'TOP_TERMS_PER_NODE':20,
  'TOP_CPC_PER_LEAF':12,
  'REPRESENTATIVE_PATENTS_PER_LEAF':12,
  'PRINT_FULL_RESULT_TABLES':True,
  'SAVE_VECTOR_FIGURES':True,
  'CREATE_FULL_ARCHIVE':True,
  'INCLUDE_DOCUMENT_METADATA_IN_PAPER_PACKAGE':True,
  'FORCE_RECOMPUTE':False,
}
# Scientific interpretation: thresholds are study-specific operational screens,
# not universal published cutoffs. All tested values, failed checks and seeds
# are retained. Branch count is intentionally absent from the selection ranking.
assert SETTINGS['MAX_DEPTH']>=1 and SETTINGS['ROOT_RESTARTS']>=3
assert 0<=SETTINGS['MIN_SEED_ARI']<=1 and SETTINGS['MIN_GAMMA']>0
assert SETTINGS['MIN_CHILD_TERMS']>=2

# %% [markdown]
# ## 2. Locate original outputs and establish immutable provenance

# %%
try:
    from google.colab import drive
    drive.mount('/content/drive', force_remount=False)
except ImportError:
    pass
if SETTINGS['PROJECT_ROOT']:
    PROJECT=Path(SETTINGS['PROJECT_ROOT']).expanduser().resolve()
elif Path('/content/drive/MyDrive').exists():
    PROJECT=Path('/content/drive/MyDrive/Academic/Circular Economy Taxonomy')
elif (Path.home()/'MyDrive/Academic/Circular Economy Taxonomy').exists():
    PROJECT=Path.home()/'MyDrive/Academic/Circular Economy Taxonomy'
else:
    PROJECT=Path.cwd()
assert PROJECT.is_dir(), f'Project folder missing: {PROJECT}'

def sha256_file(path, chunk=4*1024*1024):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(chunk), b''): h.update(b)
    return h.hexdigest()
def hjson(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,default=str,ensure_ascii=False).encode()).hexdigest()
def atomic_json(path,obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.partial')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    tmp.replace(path)
def atomic_csv(df,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.partial')
    df.to_csv(tmp,index=False,encoding='utf-8-sig')
    tmp.replace(path)
def atomic_npz(path,**items):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.partial')
    with open(tmp,'wb') as f: np.savez_compressed(f,**items)
    tmp.replace(path)
def try_load_csv(path):
    return pd.read_csv(path,low_memory=False) if Path(path).is_file() else None

relative_needed=[
 '03_network/filtered_weighted_edges.csv',
 '03_network/nodes_with_global_network_metrics.csv',
 '03_network/doc_term_binary.npz',
 '02_tables/analysis_patent_families.csv',
]
optional_files=[
 '03_network/title_term_binary.npz',
 '04_taxonomy/hierarchical_community_metrics.csv',
 '04_taxonomy/leiden_restart_stability_diagnostics.csv',
 'RUN_CONFIGURATION_AND_PROVENANCE.json',
 '02_tables/source_records_standardized.csv',
]

def candidate_source():
    if SETTINGS['PREVIOUS_RUN_DIR']:
        d=Path(SETTINGS['PREVIOUS_RUN_DIR']).expanduser()
        assert all((d/x).exists() for x in relative_needed),f'Incomplete previous run: {d}'
        return 'directory',d
    if SETTINGS['INPUT_BUNDLE_ZIP']:
        p=Path(SETTINGS['INPUT_BUNDLE_ZIP']).expanduser()
        assert p.is_file(),p
        return 'zip',p
    root=PROJECT/'CE_Technology_Tree_Outputs'
    dirs=[p for p in root.glob('*') if p.is_dir() and all((p/x).is_file() for x in relative_needed)] if root.exists() else []
    dirs.sort(key=lambda p:p.stat().st_mtime,reverse=True)
    if dirs:
        return 'directory',dirs[0]
    zips=[PROJECT/'all_outputs_bundle.zip']
    if root.exists():zips.extend(root.glob('*/all_outputs_bundle.zip'))
    zips=[x for x in zips if x.is_file()]
    zips.sort(key=lambda p:p.stat().st_mtime,reverse=True)
    if zips:return 'zip',zips[0]
    raise FileNotFoundError(f'Cannot find archived network files or all_outputs_bundle.zip under {PROJECT}')

SOURCE_KIND,SOURCE_PATH=candidate_source()
if SOURCE_KIND=='directory':
    SOURCE_DIGESTS={r:sha256_file(SOURCE_PATH/r) for r in relative_needed}
else:
    with zipfile.ZipFile(SOURCE_PATH) as z:
        missing_members=set(relative_needed)-set(z.namelist())
        if missing_members:raise ValueError('Missing ZIP members: '+str(missing_members))
        SOURCE_DIGESTS={}
        for r in relative_needed:
            with z.open(r) as stream:
                h=hashlib.sha256()
                for b in iter(lambda:stream.read(4*1024*1024),b''):h.update(b)
                SOURCE_DIGESTS[r]=h.hexdigest()
SOURCE_FINGERPRINT=hjson(SOURCE_DIGESTS)
RUN_HASH=hjson({'version':VERSION,'network':SOURCE_FINGERPRINT,
                'settings':{k:v for k,v in SETTINGS.items() if k not in
                            ('PROJECT_ROOT','PREVIOUS_RUN_DIR','INPUT_BUNDLE_ZIP',
                             'PRINT_FULL_RESULT_TABLES','CREATE_FULL_ARCHIVE',
                             'INCLUDE_DOCUMENT_METADATA_IN_PAPER_PACKAGE','FORCE_RECOMPUTE')}})[:12]
RUN_ID=f'{SOURCE_FINGERPRINT[:12]}_{RUN_HASH}'
OUT=PROJECT/SETTINGS['OPTIMIZER_FOLDER']/RUN_ID
CACHE=OUT/'00_previous_run_input_cache'
AUD=OUT/'01_selection_audit';PARTS=OUT/'02_node_checkpoints'
TREE=OUT/'03_taxonomy';EVID=OUT/'04_patent_evidence'
FIG=OUT/'05_figures';HAND=OUT/'06_paper_handoff'
LOGDIR=OUT/'07_logs'
for d in [OUT,CACHE,AUD,PARTS,TREE,EVID,FIG,HAND,LOGDIR]:d.mkdir(parents=True,exist_ok=True)
RUNLOG=LOGDIR/'OPTIMIZER_ALL_PRINTS.txt'
def say(*args):
    msg=' '.join(map(str,args))
    print(msg,flush=True)
    with RUNLOG.open('a',encoding='utf-8') as f:f.write(msg+'\n')
def show_df(df,caption,max_rows=None):
    say('\n'+'='*100+'\n'+caption+' | rows='+str(len(df)))
    if max_rows is not None: view=df.head(max_rows)
    elif SETTINGS['PRINT_FULL_RESULT_TABLES']:view=df
    else:view=df.head(50)
    s=view.to_string(index=False,max_colwidth=100)
    say(s)
    if max_rows is not None and len(df)>max_rows:say('Remaining rows stored in CSV.')

say('\n'+'#'*100)
say('AUTO LEIDEN OPTIMIZATION RUN',RUN_ID)
say('SOURCE TYPE:',SOURCE_KIND,'PATH:',SOURCE_PATH)
say('OUTPUT:',OUT,'NETWORK SHA FINGERPRINT:',SOURCE_FINGERPRINT)
say('PREPROCESSING WILL NOT BE RERUN. Completed seed and node checkpoints will be reused.')
if SOURCE_KIND=='zip':
    with zipfile.ZipFile(SOURCE_PATH) as z:
        for r in relative_needed+optional_files:
            dest=CACHE/r
            if r not in z.namelist():continue
            if dest.is_file() and (r not in SOURCE_DIGESTS or sha256_file(dest)==SOURCE_DIGESTS[r]):
                say('[CACHE] Previously extracted:',r)
                continue
            dest.parent.mkdir(parents=True,exist_ok=True)
            tmp=dest.with_name(dest.name+'.partial')
            with z.open(r) as inp, open(tmp,'wb') as out:shutil.copyfileobj(inp,out)
            tmp.replace(dest)
            if r in SOURCE_DIGESTS and sha256_file(dest)!=SOURCE_DIGESTS[r]:
                raise IOError('Extracted input SHA mismatch: '+r)
            say('[EXTRACTED ONCE]',r,'bytes',dest.stat().st_size)
    INPUT_BASE=CACHE
else:INPUT_BASE=SOURCE_PATH

# %% [markdown]
# ## 3. Load the **previous** graph and patent-term evidence (no repeated processing)

# %%
EDGES=pd.read_csv(INPUT_BASE/'03_network/filtered_weighted_edges.csv')
TERMS=pd.read_csv(INPUT_BASE/'03_network/nodes_with_global_network_metrics.csv')
B=sparse.load_npz(INPUT_BASE/'03_network/doc_term_binary.npz').tocsr()
B.data=np.ones_like(B.data,dtype=np.int32)
B=B.astype(np.int32)
DOCS=pd.read_csv(INPUT_BASE/'02_tables/analysis_patent_families.csv',low_memory=False)
assert len(DOCS)==B.shape[0],f'Document/term incidence row mismatch: {len(DOCS)} != {B.shape[0]}'
need={'source_term_id','target_term_id','edge_weight'}
assert need.issubset(EDGES.columns)
assert {'term_id','keyphrase','global_doc_frequency'}.issubset(TERMS.columns)
assert EDGES[list(need)].notna().all().all()
assert (EDGES.edge_weight>0).all()
assert EDGES[['source_term_id','target_term_id']].to_numpy().min()>=0
assert EDGES[['source_term_id','target_term_id']].to_numpy().max()<B.shape[1]
assert not EDGES.duplicated(['source_term_id','target_term_id']).any()
# Exact evidence-integrity check: verify every retained original edge against B.
_check_co=(B.T @ B).tocsr()
_u,_v=EDGES[['source_term_id','target_term_id']].to_numpy(dtype=np.int32).T
_observed_co=np.asarray(_check_co[_u,_v]).ravel()
_df=np.asarray(B.sum(axis=0)).ravel().astype(float)
_rebuilt_w=_observed_co/np.sqrt(np.maximum(1.,_df[_u]*_df[_v]))*np.log1p(_observed_co)
if 'cooccurrence_patents' in EDGES.columns:
    assert np.array_equal(_observed_co,EDGES.cooccurrence_patents.to_numpy(dtype=np.int64)), \
        'Previous network edge cooccurrence does NOT match its incidence file.'
assert np.allclose(_rebuilt_w,EDGES.edge_weight.to_numpy(dtype=float),rtol=1e-9,atol=1e-10), \
    'Previous network weights do NOT match incidence matrix / formula.'
del _check_co,_observed_co,_rebuilt_w,_df,_u,_v
vertex_ids=sorted(set(EDGES.source_term_id.astype(int))|set(EDGES.target_term_id.astype(int)))
vertex_pos={k:i for i,k in enumerate(vertex_ids)}
G=ig.Graph(n=len(vertex_ids),edges=[(vertex_pos[int(a)],vertex_pos[int(b)]) for a,b in
                   EDGES[['source_term_id','target_term_id']].itertuples(index=False,name=None)],directed=False)
G.vs['term_id']=vertex_ids
G.es['weight']=EDGES.edge_weight.astype(float).tolist()
G.es['original_edge_id']=list(range(G.ecount()))
term_text=dict(zip(TERMS.term_id.astype(int),TERMS.keyphrase.astype(str)))
term_df=dict(zip(TERMS.term_id.astype(int),TERMS.global_doc_frequency.astype(int)))
RAW_AUDIT=try_load_csv(INPUT_BASE/'04_taxonomy/hierarchical_community_metrics.csv')
SOURCE_METADATA={}
if (INPUT_BASE/'RUN_CONFIGURATION_AND_PROVENANCE.json').is_file():
    SOURCE_METADATA=json.loads((INPUT_BASE/'RUN_CONFIGURATION_AND_PROVENANCE.json').read_text(encoding='utf-8'))
if SETTINGS.get('EXPECTED_PREVIOUS_RUN_ID'):
    actual_original_run_id=SOURCE_METADATA.get('run_id','')
    if actual_original_run_id != SETTINGS['EXPECTED_PREVIOUS_RUN_ID']:
        raise ValueError(
            'SOURCE RUN ID MISMATCH: '
            f'expected {SETTINGS["EXPECTED_PREVIOUS_RUN_ID"]}; '
            f'provenance contains {actual_original_run_id!r}. '
            'Use the exact archived 42,410-record run directory.'
        )
say('[SOURCE CHECK] Original source run:',SOURCE_METADATA.get('run_id'),
    '| Patent units:',len(DOCS),'| Incidence shape:',B.shape,
    '| Lens input SHA:',SOURCE_METADATA.get('source_sha256'))
if SETTINGS['EXPECTED_ANALYTICAL_PATENT_UNITS'] is not None:
    assert len(DOCS)==SETTINGS['EXPECTED_ANALYTICAL_PATENT_UNITS'], (
        f'WRONG INPUT RUN: {len(DOCS)} patent units; expected {SETTINGS["EXPECTED_ANALYTICAL_PATENT_UNITS"]}. '+
        'This notebook is locked to the 42,410-record archived run; inspect PREVIOUS_RUN_DIR.')
if SETTINGS['EXPECTED_LENS_ZIP_SHA_PREFIX']:
    oldhash=SOURCE_METADATA.get('source_sha256','')
    if not oldhash.startswith(SETTINGS['EXPECTED_LENS_ZIP_SHA_PREFIX']):
        raise ValueError('WRONG INPUT SOURCE SHA: '+str(oldhash)+'; expected prefix '+
              SETTINGS['EXPECTED_LENS_ZIP_SHA_PREFIX']+'; select the correct previous run. '+
              'If your Lens input was intentionally changed again, manually review and update the lock.')
CC=G.connected_components()
component_sizes=sorted(CC.sizes(),reverse=True)
assert len(vertex_ids)==G.vcount()
assert np.isfinite(G.es['weight']).all() if isinstance(G.es['weight'],np.ndarray) else np.isfinite(np.asarray(G.es['weight'])).all()
if len(set(DOCS.document_id.astype(str))) != len(DOCS):
    say('WARNING: document_id not unique; use row index as analytical identity.')
input_manifest={
 'old_source_type':SOURCE_KIND,'old_source_path':str(SOURCE_PATH),
 'network_and_incidence_sha256':SOURCE_DIGESTS,'input_fingerprint':SOURCE_FINGERPRINT,
 'original_run_id':SOURCE_METADATA.get('run_id','not available'),
 'original_lens_zip_sha256':SOURCE_METADATA.get('source_sha256','not available'),
 'graph_term_nodes':G.vcount(),'retained_weighted_edges':G.ecount(),
 'patent_units':int(B.shape[0]),'candidate_phrases':int(B.shape[1]),
 'connected_components':len(CC),'largest_component_terms':max(component_sizes),
 'components_below_min_child_terms':sum(x<SETTINGS['MIN_CHILD_TERMS'] for x in component_sizes),
 'source_has_previous_leiden_metrics':RAW_AUDIT is not None,
 'collected_on':'2026-09-14 (user-reported Lens export date)',
 'references':'See 06_paper_handoff/METHOD_REFERENCES.ris'}
atomic_json(AUD/'INPUT_PROVENANCE.json',input_manifest)
atomic_json(AUD/'LOCKED_ANALYSIS_PLAN.json',{'run_id':RUN_ID,'version':VERSION,
    'settings':SETTINGS,'created_utc':datetime.now(timezone.utc).isoformat(),
    'seed_policy':'SHA256(base seed + node ID + gamma + restart + tag), deterministic integers',
    'selection_policy':'Feasibility first; ROOT document-bootstrap ARI as continuous ranking (no bootstrap cutoff); then lexicographic stability of nearby resolutions, multi-seed ARI, fraction of terms retained, lower weighted conductance; NEVER maximize number of communities',
    'caution':'Thresholds are operational, not universal published cutoffs; bootstrap fixes graph topology and reweights documents.'})
say('REUSED DATA: patent units=',B.shape[0],'; extracted phrases=',B.shape[1],
    '; active nodes=',G.vcount(),'; edges=',G.ecount())
say('CONNECTED COMPONENTS:',len(CC),'largest:',component_sizes[:20],
    'components smaller than minimum child:',sum(x<SETTINGS['MIN_CHILD_TERMS'] for x in component_sizes))
if RAW_AUDIT is not None:show_df(RAW_AUDIT,'ORIGINAL LEIDEN AUDIT (not overwritten)',max_rows=20)

# %% [markdown]
# ## 4. Candidate partitions, independent seed stability, exact acceptance gates

# %%
def node_seed(node_id, gamma, restart, tag='regular'):
    raw=f"{SETTINGS['SEED']}|{node_id}|{gamma:.6f}|{restart}|{tag}"
    return (int(hashlib.sha256(raw.encode()).hexdigest()[:8],16) % 2_000_000_000)+1

def gammas_for_node(depth,parent_gamma=None):
    if depth==0: return sorted({float(v) for v in SETTINGS['ROOT_RESOLUTIONS']})
    return sorted({round(max(SETTINGS['MIN_GAMMA'],min(SETTINGS['MAX_GAMMA'],
              float(parent_gamma)*float(mult))),5)
              for mult in SETTINGS['CHILD_GAMMA_MULTIPLIERS']})

def member_digest(ids):
    a=np.asarray(sorted(map(int,ids)),dtype='<i8')
    return hashlib.sha256(a.tobytes()).hexdigest()

def root_component_positions(g):
    largest=max(g.connected_components(),key=lambda comp:len(comp))
    return np.asarray(sorted(largest),dtype=np.int32)

def compare_partition_pairs(members,indices):
    if len(members)<2:return {'full':1.,'largest_component':1.,'pairs':[]}
    full,primary,pairs=[],[],[]
    for i,j in itertools.combinations(range(len(members)),2):
        a,b=members[i],members[j]
        f=float(adjusted_rand_score(a,b))
        p=float(adjusted_rand_score(a[indices],b[indices]))
        full.append(f);primary.append(p)
        pairs.append({'restart_i':i,'restart_j':j,'ari_all_vertices':f,
                      'ari_largest_component':p})
    return {'full':float(np.mean(full)),'largest_component':float(np.mean(primary)),'pairs':pairs}

def partition_once(g,node_id,nodehash,gamma,restart):
    seed=node_seed(node_id,gamma,restart)
    checkpoint=PARTS/node_id/f'gamma_{gamma:.5f}_restart_{restart:02d}'
    npz=Path(str(checkpoint)+'.npz'); js=Path(str(checkpoint)+'.json')
    if not SETTINGS['FORCE_RECOMPUTE'] and js.is_file() and npz.is_file():
        m=np.load(npz,allow_pickle=False)['membership']
        info=json.loads(js.read_text(encoding='utf-8'))
        if info.get('node_hash')==nodehash and len(m)==g.vcount() and info['seed']==seed:
            say('[REUSE PARTITION]',node_id,'gamma',gamma,'seed',seed,'groups',info['raw_communities'])
            return np.asarray(m,dtype=np.int32),info
    t=time.perf_counter()
    p=la.find_partition(g,la.RBConfigurationVertexPartition,weights='weight',
                        resolution_parameter=float(gamma),seed=seed,n_iterations=-1)
    m=np.asarray(p.membership,dtype=np.int32)
    # Consistent generalized modularity and improvement at each fixed gamma.
    Q=float(g.modularity(m.tolist(),weights='weight',resolution=float(gamma)))
    Q0=float(g.modularity([0]*g.vcount(),weights='weight',resolution=float(gamma)))
    info={'node_id':node_id,'node_hash':nodehash,'gamma':float(gamma),
          'restart':restart,'seed':seed,'q_gamma':Q,'q_gamma_one_group':Q0,
          'q_gamma_improvement':Q-Q0,'raw_communities':int(np.unique(m).size),
          'elapsed_seconds':round(time.perf_counter()-t,4)}
    atomic_npz(npz,membership=m)
    atomic_json(js,info)
    say('[COMPUTED PARTITION]',node_id,'gamma',gamma,'seed',seed,'Q_gain',round(Q-Q0,5),
        'raw groups',info['raw_communities'],'elapsed',info['elapsed_seconds'])
    return m,info

def patent_units_with_terms(term_ids):
    if not term_ids:return 0
    return int(np.count_nonzero(B[:,list(term_ids)].getnnz(axis=1)))

def group_quality(g,membership):
    # Weighted conductance: cut(C)/min(vol(C),vol(V\C)).
    w=np.asarray(g.es['weight'],dtype=float)
    ends=np.asarray(g.get_edgelist(),dtype=np.int32)
    unique,encoded=np.unique(membership,return_inverse=True)
    vol=np.bincount(encoded,weights=np.asarray(g.strength(weights='weight')),minlength=len(unique))
    cut=np.zeros(len(unique),dtype=float)
    if len(ends):
        a,b=encoded[ends[:,0]],encoded[ends[:,1]]
        mask=a!=b
        np.add.at(cut,a[mask],w[mask]);np.add.at(cut,b[mask],w[mask])
    total=float(vol.sum())
    den=np.minimum(vol,np.maximum(0,total-vol))
    cond=np.divide(cut,den,out=np.zeros_like(cut),where=den>0)
    return {int(k):float(v) for k,v in zip(unique,cond)}

def audit_best_partition(g,member,info,ari_full,ari_main,term_ids):
    groups=defaultdict(list)
    for t,k in zip(term_ids,member):groups[int(k)].append(int(t))
    terms_by_group=sorted(groups.items(),key=lambda pair:(-len(pair[1]),min(pair[1])))
    cond=group_quality(g,member)
    valid,residual,group_rows=[],[],[]
    for rank,(k,ids) in enumerate(terms_by_group,1):
        ids=sorted(ids)
        support=patent_units_with_terms(ids)
        okay=(len(ids)>=SETTINGS['MIN_CHILD_TERMS'] and support>=SETTINGS['MIN_CHILD_PATENT_UNITS'])
        (valid if okay else residual).append(ids)
        group_rows.append({'rank':rank,'group_id':int(k),'term_ids':ids,'term_count':len(ids),
                           'patent_unit_support_any_phrase':support,'meets_minimums':okay,
                           'weighted_conductance':cond.get(k),
                           'top_exact_terms':' | '.join(term_text.get(t,str(t)) for t in
                             sorted(ids,key=lambda x:(-term_df.get(x,0),term_text.get(x,'')))[:12])})
    residual_ids=sorted(t for ids in residual for t in ids)
    valid_group_ids={r['group_id'] for r in group_rows if r['meets_minimums']}
    valid_conductance=[r['weighted_conductance'] for r in group_rows if r['group_id'] in valid_group_ids]
    gates={
       'at_least_two_eligible_children': len(valid)>=2,
       'child_capacity': len(valid)+bool(residual_ids)<=SETTINGS['MAX_CHILDREN_INCLUDING_RESIDUAL'],
       'residual_term_fraction': len(residual_ids)<=SETTINGS['MAX_RESIDUAL_TERM_FRACTION']*len(term_ids),
       'within_gamma_quality_improvement': info['q_gamma_improvement']>=SETTINGS['MIN_MODULARITY_IMPROVEMENT'],
       'seed_stability_largest_component': ari_main>=SETTINGS['MIN_SEED_ARI'],
    }
    metrics={'node_id':info['node_id'],'gamma':float(info['gamma']),
             'q_gamma':info['q_gamma'],'q_gamma_improvement':info['q_gamma_improvement'],
             'original_communities':int(info['raw_communities']),
             'eligible_children':len(valid),'invalid_small_groups':len(residual),
             'residual_terms':len(residual_ids),
             'residual_fraction':len(residual_ids)/max(1,len(term_ids)),
             'children_including_residual':len(valid)+bool(residual_ids),
             'seed_ari_full':float(ari_full),'seed_ari_largest_component':float(ari_main),
             'median_valid_conductance':float(np.median(valid_conductance)) if valid_conductance else 1.0,
             'feasible_all_primary_gates':all(gates.values()),
             **{f'gate_{k}':bool(v) for k,v in gates.items()},
             'failed_checks':'; '.join(k for k,v in gates.items() if not v)}
    return metrics,group_rows,valid,residual_ids

# %% [markdown]
# ## 5. Document-level bootstrap: reweight real patent incidence without rebuilding text

# %%
GLOBAL_EDGE_ENDPOINTS=EDGES[['source_term_id','target_term_id']].to_numpy(dtype=np.int32)

def reweighted_global_edges(bootstrap_seed):
    rng=np.random.default_rng(int(bootstrap_seed))
    draw=rng.integers(0,B.shape[0],size=B.shape[0])
    weights=np.bincount(draw,minlength=B.shape[0]).astype(np.int32)
    # Sparse incidence multiplication, per-document bootstrap frequency.
    WB=B.multiply(weights[:,None]).tocsr()
    cross=(B.T @ WB).tocsr()
    u,v=GLOBAL_EDGE_ENDPOINTS[:,0],GLOBAL_EDGE_ENDPOINTS[:,1]
    c=np.asarray(cross[u,v]).ravel().astype(float)
    f=np.asarray(B.T @ weights).ravel().astype(float)
    cosine=c/np.sqrt(np.maximum(1.,f[u]*f[v]))
    w=cosine*np.log1p(c)
    return np.maximum(w,1e-12),int((w<=0).sum())

def bootstrap_gamma_root(g,node_id,nodehash,gamma,baseline_membership):
    js=AUD/f'ROOT_BOOTSTRAP_{gamma:.5f}.json'
    if js.is_file() and not SETTINGS['FORCE_RECOMPUTE']:
        old=json.loads(js.read_text(encoding='utf-8'))
        if old.get('node_hash')==nodehash:
            say('[REUSE ROOT BOOTSTRAP]',gamma,'ARI',old.get('bootstrap_mean_ari'))
            return old
    main_idx=root_component_positions(g)
    edge_ids=np.asarray(g.es['original_edge_id'],dtype=np.int32)
    comparisons=[]
    for rep in range(SETTINGS['ROOT_BOOTSTRAP_REPLICATES']):
        seed=node_seed('ROOT_BOOT',gamma,rep,'document_bootstrap')
        w,n_zero=reweighted_global_edges(seed)
        perturbed=g.copy()
        perturbed.es['weight']=np.asarray(w)[edge_ids].tolist()
        part=la.find_partition(perturbed,la.RBConfigurationVertexPartition,
              weights='weight',resolution_parameter=float(gamma),
              seed=node_seed('BOOT_PART',gamma,rep),n_iterations=-1)
        m=np.asarray(part.membership,dtype=np.int32)
        comparisons.append({'gamma':gamma,'replicate':rep,'bootstrap_seed':seed,
            'ari_largest_component':float(adjusted_rand_score(baseline_membership[main_idx],m[main_idx])),
            'ari_all_vertices':float(adjusted_rand_score(baseline_membership,m)),
            'edges_zero_after_document_bootstrap':n_zero})
    score=float(np.mean([x['ari_largest_component'] for x in comparisons]))
    ans={'gamma':gamma,'node_hash':nodehash,'bootstrap_mean_ari':score,
         'replicate_details':comparisons,
         'interpretation':'Document multinomial bootstrap, fixed graph topology; new edges are NOT discovered.'}
    atomic_json(js,ans)
    say('[ROOT BOOTSTRAP]',gamma,'mean ARI largest component',round(score,4))
    return ans

# %% [markdown]
# ## 6. Predeclared automatic model selection and recursive parent–child hierarchy

# %%
def evaluate_node(node_id,term_ids,depth,parent_id='',parent_gamma=None,residual=False):
    term_ids=sorted(map(int,term_ids))
    nodehash=member_digest(term_ids)
    selected_path=PARTS/node_id/'FINAL_NODE_DECISION.json'
    if selected_path.is_file() and not SETTINGS['FORCE_RECOMPUTE']:
        saved=json.loads(selected_path.read_text(encoding='utf-8'))
        if saved.get('term_ids_hash')!=nodehash or saved.get('depth')!=depth:
            raise RuntimeError('Node checkpoint source mismatch: '+str(selected_path))
        say('[RESUME NODE]',node_id,'depth',depth,'selected gamma',saved.get('selected_gamma'),
            'children',len(saved.get('children',[])),'decision',saved.get('stop_reason'))
        return saved
    g=G.induced_subgraph([vertex_pos[t] for t in term_ids])
    actual_order=list(map(int,g.vs['term_id']))
    assert actual_order==term_ids,'igraph induced order differs from expected order'
    record={'node_id':node_id,'parent_id':parent_id,'depth':depth,
            'term_ids_hash':nodehash,'term_ids':term_ids,'term_count':len(term_ids),
            'edge_count':g.ecount(),'patent_support':patent_units_with_terms(term_ids),
            'parent_gamma':parent_gamma,'selected_gamma':None,'split_accepted':False,
            'residual':bool(residual),'children':[], 'stop_reason':'',
            'candidate_gamma_metrics':[],'pairwise_aris':[],'restarts':[],
            'selected_group_diagnostics':[],'bootstrap':[]}
    reasons=[]
    if residual: reasons.append('residual_disconnected_or_small_groups_are_terminal')
    if depth>=SETTINGS['MAX_DEPTH']:reasons.append('depth_limit')
    if len(term_ids)<SETTINGS['MIN_PARENT_TERMS']:reasons.append('below_parent_term_minimum')
    if g.ecount()<2:reasons.append('fewer_than_two_internal_edges')
    if record['patent_support']<2*SETTINGS['MIN_CHILD_PATENT_UNITS']:
        reasons.append('insufficient_parent_patent_evidence')
    if reasons:
        record['stop_reason']='; '.join(reasons)
        atomic_json(selected_path,record)
        return record

    grid=gammas_for_node(depth,parent_gamma)
    main_idx=root_component_positions(g)
    all_candidates=[]
    for gamma in grid:
        repeats=SETTINGS['ROOT_RESTARTS'] if depth==0 else SETTINGS['CHILD_RESTARTS']
        runs=[partition_once(g,node_id,nodehash,gamma,k) for k in range(repeats)]
        parts=[a for a,b in runs]
        for m,info in runs:record['restarts'].append(info)
        compare=compare_partition_pairs(parts,main_idx)
        for pair in compare['pairs']:
            record['pairwise_aris'].append({'node_id':node_id,'gamma':gamma,**pair})
        # Compare objective quality within gamma, NEVER across gamma.
        winner_idx=max(range(len(runs)),key=lambda k:runs[k][1]['q_gamma_improvement'])
        best_m,best_info=runs[winner_idx]
        met,group_rows,valid,residual_ids=audit_best_partition(
            g,best_m,best_info,compare['full'],compare['largest_component'],actual_order)
        met.update({'node_id':node_id,'depth':depth,'selected_restart':winner_idx,
                    'selected_seed':best_info['seed'],'scale_neighbor_ari':None,
                    'bootstrap_mean_ari':None,'bootstrap_gate_status':'not tested'})
        all_candidates.append({'gamma':gamma,'metrics':met,'membership':best_m,
                               'groups':group_rows,'valid':valid,'residual':residual_ids})
        record['candidate_gamma_metrics'].append(met)
        # Save an up-to-date checkpoint even if a notebook stops midway through another node.
        atomic_json(PARTS/node_id/'PARTIAL_GAMMA_SCAN.json',
                    {'term_ids_hash':nodehash,'completed_gammas':[c['gamma'] for c in all_candidates],
                     'metrics':record['candidate_gamma_metrics']})

    # Scale-neighborhood continuity: compare neighboring tested resolutions on SAME node labels.
    for i,c in enumerate(all_candidates):
        nearby=[]
        for j in (i-1,i+1):
            if 0<=j<len(all_candidates):
                nearby.append(float(adjusted_rand_score(
                    c['membership'][main_idx],all_candidates[j]['membership'][main_idx])))
        c['metrics']['scale_neighbor_ari']=float(np.mean(nearby)) if nearby else np.nan
    record['candidate_gamma_metrics']=[c['metrics'] for c in all_candidates]
    feasible=[c for c in all_candidates if c['metrics']['feasible_all_primary_gates']]

    # Lexicographic stability-first sorting; number of groups is NEVER optimized.
    # Candidates with high scale continuity rank first, then reproducibility across
    # seeds, then non-residual coverage, lower conductance, and coarser gamma tie break.
    def score(c):
        x=c['metrics']
        return (-x['scale_neighbor_ari'],-x['seed_ari_largest_component'],
                x['residual_fraction'],x['median_valid_conductance'],x['gamma'])
    feasible.sort(key=score)
    if depth==0 and feasible and SETTINGS['ROOT_BOOTSTRAP_REPLICATES']>0:
        top=(feasible if SETTINGS['ROOT_BOOTSTRAP_CANDIDATES']==0 else feasible[:SETTINGS['ROOT_BOOTSTRAP_CANDIDATES']])
        boot_results={}
        for c in top:
            boot=bootstrap_gamma_root(g,node_id,nodehash,c['gamma'],c['membership'])
            boot_results[c['gamma']]=boot
            c['metrics']['bootstrap_mean_ari']=boot['bootstrap_mean_ari']
            c['metrics']['bootstrap_gate_status']='ranked_continuous_not_a_gate'
            record['bootstrap'].extend(boot['replicate_details'])
        # ROOT: primary criterion is document-bootstrap reproducibility, followed by
        # resolution neighborhood, random-seed agreement, residual and conductance.
        # No arbitrary 0.50 document-bootstrap cutoff or maximizing group count.
        feasible=sorted(top,key=lambda c:(-c['metrics']['bootstrap_mean_ari'],*score(c)))
    record['candidate_gamma_metrics']=[c['metrics'] for c in all_candidates]
    if not feasible:
        record['stop_reason']='no_gamma_satisfies_declared_structural_and_stability_gates'
        record['failures_by_gamma']=[{'gamma':c['gamma'],'failed_checks':c['metrics']['failed_checks'],
                                     'bootstrap_gate_status':c['metrics']['bootstrap_gate_status']}
                                    for c in all_candidates]
        atomic_json(selected_path,record)
        say('[NO ACCEPTABLE SPLIT]',node_id,'reason',record['stop_reason'])
        return record
    chosen=feasible[0]
    record['selected_gamma']=chosen['gamma']
    record['selected_seed']=chosen['metrics']['selected_seed']
    record['split_accepted']=True
    record['stop_reason']='split_accepted_by_stability_first_multiresolution_rule'
    record['selected_metrics']=chosen['metrics']
    record['selected_group_diagnostics']=chosen['groups']
    idx=0
    for group in chosen['valid']:
        idx+=1
        cid=('T'+f'{idx:02d}') if node_id=='ROOT' else node_id+'.'+f'{idx:02d}'
        record['children'].append({'node_id':cid,'term_ids':sorted(group),'depth':depth+1,
           'patent_support':patent_units_with_terms(group),
           'residual':False,'parent_gamma':chosen['gamma']})
    if chosen['residual']:
        cid=('TR') if node_id=='ROOT' else node_id+'.R'
        record['children'].append({'node_id':cid,'term_ids':sorted(chosen['residual']),
            'depth':depth+1,'patent_support':patent_units_with_terms(chosen['residual']),
            'residual':True,'parent_gamma':chosen['gamma']})
    children_term_ids=[x for ch in record['children'] for x in ch['term_ids']]
    assert len(children_term_ids)==len(set(children_term_ids))
    assert set(children_term_ids)==set(term_ids)
    atomic_json(selected_path,record)
    say('[ACCEPTED]',node_id,'gamma',record['selected_gamma'],
        'number children',len(record['children']),
        'ARI',chosen['metrics']['seed_ari_largest_component'],
        'plateau',chosen['metrics']['scale_neighbor_ari'])
    return record

# %%
# Execution cap is an operational resource guard, NOT a scientific model parameter.
# Intentionally keep SETTINGS, VERSION, and the original RUN_ID UNCHANGED so all
# previous seed/node/root-bootstrap checkpoints remain addressable in their folder.
# To extend again, change only this value; do not edit SETTINGS['MAX_NODES'].
RUNTIME_MAX_NODES = 1500
assert isinstance(RUNTIME_MAX_NODES, int) and RUNTIME_MAX_NODES >= SETTINGS['MAX_NODES']
EXECUTION_CAP_AUDIT = AUD/'EXECUTION_CAP_EXTENSION.json'
atomic_json(EXECUTION_CAP_AUDIT, {
    'run_id': RUN_ID,
    'source_fingerprint': SOURCE_FINGERPRINT,
    'original_settings_max_nodes': SETTINGS['MAX_NODES'],
    'effective_execution_only_node_limit': RUNTIME_MAX_NODES,
    'model_selection_settings_unchanged': True,
    'seed_and_resolution_settings_unchanged': True,
    'reason': ('The original 200-node guard was reached before recursion ended. '
               'Increasing this execution-only limit does not relax any scientific '
               'split acceptance gate or alter source inputs.'),
    'updated_utc': datetime.now(timezone.utc).isoformat(),
})
say('[RESUME] Same RUN_ID:', RUN_ID)
say('[RESUME] Existing checkpoint directory:', PARTS)
say('[RESUME] Execution safety cap raised from', SETTINGS['MAX_NODES'],
    'to', RUNTIME_MAX_NODES, 'without changing scientific settings or RUN_ID.')
say('[RESUME] Replaying branch tree from ROOT using FINAL_NODE_DECISION.json; '
    'completed evaluations will be loaded, not recomputed.')

# Replay the breadth-first queue deterministically from ROOT. Existing node
# checkpoints are read in evaluate_node(); only unfinished nodes are computed.
# This reconstruction also guards against an interrupted notebook that lost its
# in-memory queue. No 'partial taxonomy' is exported as a completed result.
queue = deque([{'node_id':'ROOT','term_ids':vertex_ids,'depth':0,
               'parent_id':'','parent_gamma':None,'residual':False}])
NODE_RESULTS = {}
reused_nodes = 0
new_nodes = 0

def save_recursion_progress(state):
    atomic_json(AUD/'RECURSION_PROGRESS.json', {
        'run_id': RUN_ID,
        'source_fingerprint': SOURCE_FINGERPRINT,
        'state': state,
        'completed_count': len(NODE_RESULTS),
        'reused_count': reused_nodes,
        'new_count': new_nodes,
        'pending_count': len(queue),
        'pending_node_ids': [item['node_id'] for item in queue],
        'effective_execution_only_node_limit': RUNTIME_MAX_NODES,
        'updated_utc': datetime.now(timezone.utc).isoformat(),
    })

save_recursion_progress('running')
while queue:
    # Check BEFORE removing the next node. All previously completed nodes stay
    # persisted in independent JSON checkpoints in 02_node_checkpoints/.
    if len(NODE_RESULTS) >= RUNTIME_MAX_NODES:
        save_recursion_progress('paused_at_execution_cap')
        say('EXECUTION SAFETY CAP REACHED:', RUNTIME_MAX_NODES,
            '| completed:', len(NODE_RESULTS), '| pending:', len(queue))
        say('Only increase RUNTIME_MAX_NODES in this cell and rerun it. '
            'Do NOT change SETTINGS or RUN_ID; do NOT rerun preprocessing.')
        raise RuntimeError('Execution cap reached. Tree incomplete; saved nodes are reusable.')
    item = queue.popleft()
    if item['node_id'] in NODE_RESULTS:
        raise RuntimeError('Repeated branch ID: ' + str(item['node_id']))
    checkpoint_path = PARTS/item['node_id']/'FINAL_NODE_DECISION.json'
    was_checkpointed = checkpoint_path.is_file() and not SETTINGS['FORCE_RECOMPUTE']
    result = evaluate_node(**item)
    NODE_RESULTS[item['node_id']] = result
    reused_nodes += int(was_checkpointed)
    new_nodes += int(not was_checkpointed)
    for child in result['children']:
        queue.append({'node_id': child['node_id'], 'term_ids': child['term_ids'],
            'depth': child['depth'], 'parent_id': result['node_id'],
            'parent_gamma': child['parent_gamma'], 'residual': child['residual']})
    say('[PROGRESS] completed nodes', len(NODE_RESULTS),
        '| loaded checkpoints', reused_nodes, '| newly evaluated', new_nodes,
        '| queue remaining', len(queue))
    if len(NODE_RESULTS) % 10 == 0:
        save_recursion_progress('running')

save_recursion_progress('complete')
say('[RECURSION COMPLETE] total nodes', len(NODE_RESULTS),
    '| loaded from prior checkpoints', reused_nodes,
    '| newly evaluated', new_nodes,
    '| queue remaining', len(queue))
assert not queue
assert len(NODE_RESULTS) <= RUNTIME_MAX_NODES

# %% [markdown]
# ## 7. Publish every searched gamma, every stop decision and complete tree membership

# %%
metrics_rows,scan_rows,seed_rows,ari_rows,branch_term_rows,group_rows,boot_rows=[],[],[],[],[],[],[]
for n in NODE_RESULTS.values():
    metrics_rows.append({k:v for k,v in n.items() if k not in
        ('term_ids','children','candidate_gamma_metrics','pairwise_aris','restarts',
         'selected_group_diagnostics','bootstrap','failures_by_gamma','selected_metrics')})
    for row in n['candidate_gamma_metrics']:scan_rows.append(row)
    for row in n['restarts']:seed_rows.append(row)
    for row in n['pairwise_aris']:ari_rows.append(row)
    for row in n['bootstrap']:boot_rows.append({'node_id':n['node_id'],**row})
    for row in n['selected_group_diagnostics']:
        group_rows.append({'node_id':n['node_id'],'chosen_gamma':n['selected_gamma'],**row})
    for tid in n['term_ids']:
        branch_term_rows.append({'node_id':n['node_id'],'parent_id':n['parent_id'],
           'depth':n['depth'],'term_id':int(tid),'exact_phrase':term_text.get(int(tid),''),
           'is_leaf':not bool(n['children']),'is_residual':bool(n['residual'])})
NODE_METRICS=pd.DataFrame(metrics_rows)
SCANS=pd.DataFrame(scan_rows)
SEEDS=pd.DataFrame(seed_rows)
ARIS=pd.DataFrame(ari_rows)
MEMBERSHIPS=pd.DataFrame(branch_term_rows)
SELECTED_GROUPS=pd.DataFrame(group_rows)
BOOTSTRAPS=pd.DataFrame(boot_rows)
for df,name in [
 (NODE_METRICS,'ALL_NODE_DECISIONS'),(SCANS,'EVERY_GAMMA_EVERY_GATE'),
 (SEEDS,'EVERY_RANDOM_SEED_PARTITION'),(ARIS,'ALL_PAIRWISE_ARI'),
 (MEMBERSHIPS,'ALL_HIERARCHICAL_TERM_MEMBERSHIPS'),
 (SELECTED_GROUPS,'ALL_SELECTED_GROUPS_WITH_EXACT_TERMS'),
 (BOOTSTRAPS,'ROOT_DOCUMENT_BOOTSTRAP_DETAILS')]:
    atomic_csv(df,AUD/(name+'.csv'))
    say('[SAVED]',name,'rows',len(df))

# Validate rooted partition (at every split and across terminal leaves).
leaves=[n for n in NODE_RESULTS.values() if not n['children']]
leaf_union=[t for n in leaves for t in n['term_ids']]
assert len(leaf_union)==len(set(leaf_union)), 'Leaves overlap in term membership!'
assert set(leaf_union)==set(vertex_ids), 'Some original graph terms lost during recursion!'
assert set(NODE_RESULTS)=={x['node_id'] for x in NODE_RESULTS.values()}
# Counterfactual gate sensitivity is an AUDIT ONLY; it never chooses the model.
# The reported selected tree always uses the locked settings above.
GATE_COUNTERFACTUAL=[]
base_root=SCANS[SCANS.node_id=='ROOT']
for _,r in base_root.iterrows():
    for cap in (10,12,15,20,25,35):
        for ari_cut in (0.45,0.55,0.65,0.75):
            for residual_cut in (0.15,0.25,0.35):
                passed=(r.eligible_children>=2 and
                   r.children_including_residual<=cap and
                   r.residual_fraction<=residual_cut and
                   r.q_gamma_improvement>=SETTINGS['MIN_MODULARITY_IMPROVEMENT'] and
                   r.seed_ari_largest_component>=ari_cut)
                GATE_COUNTERFACTUAL.append({'gamma':r.gamma,
                    'assumed_child_cap':cap,'assumed_min_seed_ari':ari_cut,
                    'assumed_max_residual_fraction':residual_cut,
                    'would_pass_structural_gates':bool(passed),
                    'note':'DESCRIPTIVE COUNTERFACTUAL: not used for selecting the final tree'})
atomic_csv(pd.DataFrame(GATE_COUNTERFACTUAL),AUD/'COUNTERFACTUAL_GATE_SENSITIVITY_NOT_USED_FOR_SELECTION.csv')
show_df(NODE_METRICS,'EVERY FINAL NODE AND EXACT STOP DECISION')
show_df(SCANS,'ALL TRIED GAMMAS, FAILED GATES, ROOT BOOTSTRAP AND STABILITY')
show_df(SELECTED_GROUPS,'ALL SELECTED CHILD GROUP TERMS AND PATENT SUPPORT',max_rows=250)

# %% [markdown]
# ## 8. Label using **literal patent vocabulary** and export overlapping patent support

# %%
# Every detected term has ONE terminal node, but a patent may hit MANY leaves.
root_depth=max(n['depth'] for n in NODE_RESULTS.values())
for node in NODE_RESULTS.values():
    ids=node['term_ids']
    ids_sorted=sorted(ids,key=lambda t:(-term_df.get(t,0),-len(term_text.get(t,'').split()),term_text.get(t,'')))
    node['top_exact_phrases']=[{'phrase':term_text.get(t,''),'term_id':t,
                 'global_patent_units':term_df.get(t,0)} for t in ids_sorted[:SETTINGS['TOP_TERMS_PER_NODE']]]
    node['provisional_data_label']=' / '.join(x['phrase'] for x in node['top_exact_phrases'][:3])

node_table=pd.DataFrame([{
 'node_id':n['node_id'],'parent_id':n['parent_id'],'depth':n['depth'],
 'is_terminal':not bool(n['children']),'is_residual':n['residual'],
 'patent_support_any_phrase':n['patent_support'],
 'term_count':n['term_count'],'edge_count':n['edge_count'],
 'resolution_chosen':n.get('selected_gamma'),
 'seed_chosen':n.get('selected_seed'),
 'provisional_exact_phrase_label':n['provisional_data_label'],
 'top_20_exact_phrases':' | '.join(x['phrase'] for x in n['top_exact_phrases']),
 'stop_reason':n['stop_reason']}
 for n in NODE_RESULTS.values()])
atomic_csv(node_table,TREE/'FULL_HIERARCHY_NODE_TABLE.csv')
# GraphML is lossless for the parent/child topology and retains numeric metadata.
h=nx.DiGraph()
for n in NODE_RESULTS.values():
    h.add_node(n['node_id'],depth=int(n['depth']),
               term_count=int(n['term_count']),patent_units=int(n['patent_support']),
               provisional_phrase_label=n['provisional_data_label'],
               residual=int(n['residual']),selected_gamma=float(n['selected_gamma'] or 0))
    for child in n['children']:h.add_edge(n['node_id'],child['node_id'])
nx.write_graphml(h,TREE/'HIERARCHICAL_TAXONOMY.graphml')
atomic_json(TREE/'FULL_REPRODUCIBLE_TREE.json',{ 
  'source_fingerprint':SOURCE_FINGERPRINT,'run_id':RUN_ID,
  'root_id':'ROOT','algorithm':'Leiden RBConfiguration (multiresolution stability-first)',
  'nodes':[{**{k:v for k,v in n.items() if k not in
             ('candidate_gamma_metrics','pairwise_aris','restarts','selected_group_diagnostics',
              'bootstrap')},'children':[c['node_id'] for c in n['children']]}
           for n in NODE_RESULTS.values()]})

leaf_nodes=[n for n in leaves if not n['residual']]
leaf_ids=[n['node_id'] for n in leaf_nodes]
hits=np.zeros((B.shape[0],len(leaf_nodes)),dtype=np.int16)
for j,node in enumerate(leaf_nodes):
    hits[:,j]=np.asarray(B[:,node['term_ids']].getnnz(axis=1)).ravel().astype(np.int16)
max_hits=hits.max(axis=1) if len(leaf_nodes) else np.zeros(B.shape[0],dtype=np.int16)
primary_index=hits.argmax(axis=1) if len(leaf_nodes) else np.zeros(B.shape[0],dtype=int)
primary_id=[leaf_ids[primary_index[i]] if max_hits[i]>0 else 'UNMAPPED' for i in range(B.shape[0])]
ambiguous=[int((hits[i]==max_hits[i]).sum()>1) if max_hits[i]>0 else 0 for i in range(B.shape[0])]
DOCUMENT_IDS=(DOCS['document_id'].astype(str).tolist() if 'document_id' in DOCS else
              [f'ROW_{i:06d}' for i in range(len(DOCS))])
primary_df=pd.DataFrame({'document_id':DOCUMENT_IDS,'primary_leaf_id':primary_id,
                         'primary_match_count':max_hits.astype(int),
                         'ambiguous_max_hit_tie':ambiguous,'document_row_index':np.arange(len(DOCS))})
atomic_csv(primary_df,EVID/'PATENT_PRIMARY_HEURISTIC_ASSIGNMENT.csv')
multiple_rows=[]
for j,node in enumerate(leaf_nodes):
    rows=np.flatnonzero(hits[:,j]>0)
    multiple_rows.extend({'document_id':DOCUMENT_IDS[i],
                          'leaf_id':node['node_id'],'matching_distinct_exact_phrases':int(hits[i,j]),
                          'document_row_index':int(i)} for i in rows)
multiple_df=pd.DataFrame(multiple_rows,columns=['document_id','leaf_id',
                              'matching_distinct_exact_phrases','document_row_index'])
atomic_csv(multiple_df,EVID/'PATENT_MULTIPLE_LEAF_MEMBERSHIPS.csv')

# Store every exact phrase in every leaf. Names are evidence labels, NOT validated technology classes.
kw_rows=[]
for n in NODE_RESULTS.values():
    phrase_order=sorted(n['term_ids'],key=lambda t:(-term_df.get(t,0),term_text.get(t,'')))
    for rank,t in enumerate(phrase_order,1):
        kw_rows.append({'node_id':n['node_id'],'depth':n['depth'],'is_terminal':not n['children'],
         'is_residual':n['residual'],'rank_by_global_patent_frequency':rank,
         'term_id':t,'exact_keyphrase':term_text.get(t,''),
         'global_patent_unit_frequency':term_df.get(t,0),
         'ngram_length':len(term_text.get(t,'').split())})
all_keywords=pd.DataFrame(kw_rows)
atomic_csv(all_keywords,EVID/'ALL_EXACT_KEYPHRASES_EVERY_LEVEL.csv')
leaf_summary=[]; patent_examples=[]; cpc_rows=[]
for j,n in enumerate(leaf_nodes):
    ix=np.flatnonzero(hits[:,j]>0)
    support=len(ix)
    leaf_summary.append({'leaf_id':n['node_id'],'parent_id':n['parent_id'],
         'depth':n['depth'],'term_count':n['term_count'],
         'supporting_patent_units':support,
         'fraction_of_original_patent_units_with_a_matching_leaf_phrase':support/max(1,len(DOCS)),
         'provisional_exact_phrase_label':n['provisional_data_label'],
         'top_exact_phrases':' | '.join(x['phrase'] for x in n['top_exact_phrases'])})
    order=sorted(ix,key=lambda i:(-int(hits[i,j]),i))[:SETTINGS['REPRESENTATIVE_PATENTS_PER_LEAF']]
    for rank,i in enumerate(order,1):
        row=DOCS.iloc[int(i)]
        patent_examples.append({'leaf_id':n['node_id'],'rank':rank,'document_id':DOCUMENT_IDS[i],
          'matched_leaf_phrases':int(hits[i,j]),'title':str(row.get('title','')),
          'abstract':str(row.get('abstract',''))[:2400],
          'lens_id':str(row.get('lens_id','')),'cpc':str(row.get('cpc','')),
          'priority_year':row.get('priority_year',None),'url':str(row.get('url',''))})
    cpc_field='all_cpc' if 'all_cpc' in DOCS.columns else 'cpc'
    cpc_counts=Counter()
    for i in ix:
        # Normalized CPC subgroup (letter+two digits+letter; e.g. B29B).
        codes=set(re.findall(r'\b[A-HY]\d\d[A-Z]\b',str(DOCS.iloc[int(i)].get(cpc_field,''))))
        cpc_counts.update(codes)
    for rank,(code,count) in enumerate(cpc_counts.most_common(SETTINGS['TOP_CPC_PER_LEAF']),1):
        cpc_rows.append({'leaf_id':n['node_id'],'rank':rank,'cpc_subclass':code,
          'supporting_units_with_cpc_subclass':count,'leaf_supporting_units':support})
leaf_summary_df=pd.DataFrame(leaf_summary)
atomic_csv(leaf_summary_df,TREE/'LEAF_TECHNOLOGY_CANDIDATES.csv')
atomic_csv(pd.DataFrame(patent_examples),EVID/'REPRESENTATIVE_PATENTS_PER_LEAF.csv')
atomic_csv(pd.DataFrame(cpc_rows),EVID/'CPC_SUBCLASS_PROFILES_PER_LEAF.csv')
show_df(node_table,'FULL TECHNOLOGY CANDIDATE HIERARCHY')
show_df(leaf_summary_df,'ALL TERMINAL NONRESIDUAL LEAVES')
say('PRIMARY COVERAGE:',sum(primary_df.primary_leaf_id!='UNMAPPED'),'/',len(primary_df),
    'ambiguous ties:',sum(primary_df.ambiguous_max_hit_tie))
say('MULTIPLE LEAF MEMBERSHIP ROWS:',len(multiple_df),'(overlap retained)')

# %% [markdown]
# ## 9. Readable taxonomy figures, numeric source tables and publication-ready exports

# %%
def lineage(nid):
    out=[]
    while nid:
        out.append(nid);nid=NODE_RESULTS[nid]['parent_id']
    return list(reversed(out))

def tree_lines(node_id='ROOT',prefix='',last=True):
    n=NODE_RESULTS[node_id]
    line=prefix+('└── ' if last else '├── ')+node_id+': '+n['provisional_data_label']
    line+=f" | {n['term_count']} terms | {n['patent_support']} patent units"
    if n['residual']:line+=' | RESIDUAL / NOT A TECHNOLOGY LEAF'
    if n['selected_gamma'] is not None:line+=f" | chosen γ={n['selected_gamma']}"
    result=[line]
    children=n['children']
    for i,c in enumerate(children):
        result+=tree_lines(c['node_id'],prefix+('    ' if last else '│   '),i==len(children)-1)
    return result
TEXT_TREE='\n'.join(tree_lines())
(TREE/'TECHNOLOGY_TREE_READABLE.txt').write_text(TEXT_TREE,encoding='utf-8')
say('\nCOMPLETE TECHNOLOGY HIERARCHY\n'+TEXT_TREE)

# Figure 1: selection audit, actual gamma metrics (NEVER a schematic placeholder).
root_scan=SCANS[SCANS.node_id=='ROOT'].sort_values('gamma').copy()
if not root_scan.empty:
    fig,ax=plt.subplots(figsize=(10.5,5.4))
    ax.plot(root_scan.gamma,root_scan.seed_ari_largest_component,'o-',label='Mean seed ARI (largest component)')
    ax.plot(root_scan.gamma,root_scan.scale_neighbor_ari,'s-',label='Neighbor-resolution ARI')
    ax.axhline(SETTINGS['MIN_SEED_ARI'],ls='--',color='grey',label='Seed-stability screen')
    good=root_scan[root_scan.feasible_all_primary_gates]
    ax.scatter(good.gamma,good.seed_ari_largest_component,marker='o',s=115,facecolors='none',
               edgecolors='black',label='Structurally feasible')
    selected=NODE_RESULTS['ROOT'].get('selected_gamma')
    if selected is not None:ax.axvline(selected,ls=':',color='tab:orange',label=f'Selected γ={selected:g}')
    ax.set(xlabel='Leiden RBConfiguration resolution γ',ylabel='Adjusted Rand index',
           title='ROOT parameter sensitivity: stability and scale continuity')
    ax.grid(alpha=.17);ax.legend(loc='best',fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG/'FIG_01_ROOT_STABILITY.svg',bbox_inches='tight')
    fig.savefig(FIG/'FIG_01_ROOT_STABILITY.png',dpi=220,bbox_inches='tight');plt.close(fig)
    atomic_csv(root_scan,FIG/'FIG_01_ROOT_STABILITY_SOURCE_DATA.csv')
    fig,ax=plt.subplots(figsize=(10.5,5.4))
    ax.plot(root_scan.gamma,root_scan.eligible_children,'o-',label='Eligible children')
    ax.plot(root_scan.gamma,root_scan.children_including_residual,'s-',label='Including residual')
    ax.axhline(SETTINGS['MAX_CHILDREN_INCLUDING_RESIDUAL'],color='grey',ls='--',label='Child cap')
    if selected is not None:ax.axvline(selected,ls=':',color='tab:orange',label='Selected gamma')
    ax.set(xlabel='Leiden resolution γ',ylabel='Number of child groups',
           title='ROOT parameter sensitivity: number of eligible groups')
    ax.grid(alpha=.16);ax.legend(fontsize=8);fig.tight_layout()
    fig.savefig(FIG/'FIG_02_CHILD_CAP.svg',bbox_inches='tight')
    fig.savefig(FIG/'FIG_02_CHILD_CAP.png',dpi=220,bbox_inches='tight');plt.close(fig)
    atomic_csv(root_scan,FIG/'FIG_02_CHILD_CAP_SOURCE_DATA.csv')

# Full tree as interactive SUNBURST (arbitrary depth); all values = node term sizes.
labels,parents,ids,values=[],[],[],[]
for n in NODE_RESULTS.values():
    ids.append(n['node_id']);parents.append(n['parent_id']);values.append(int(n['term_count']))
    labels.append(n['node_id']+' | '+n['provisional_data_label'][:65]+(' [residual]' if n['residual'] else ''))
fig=go.Figure(go.Sunburst(ids=ids,labels=labels,parents=parents,values=values,
         branchvalues='total',hovertemplate='%{label}<br>terms=%{value}<extra></extra>'))
fig.update_layout(title='Nested Leiden hierarchy (term count; residual nodes marked)',
                  width=1100,height=760,margin=dict(l=12,r=12,t=65,b=12))
fig.write_html(str(FIG/'FIG_03_COMPLETE_INTERACTIVE_TREE.html'),include_plotlyjs=True)
atomic_csv(node_table,FIG/'FIG_03_INTERACTIVE_TREE_SOURCE_DATA.csv')

# Publication-quality hierarchy: a full root overview plus per-root-child pages.
# Every rectangle uses exact node labels and counts; SVG stays searchable/readable.
def render_branch(root_id,outname,max_depth_to_draw=3):
    root=NODE_RESULTS[root_id]
    subset=[n for n in NODE_RESULTS.values() if root_id in lineage(n['node_id'])
            and n['depth']-root['depth']<=max_depth_to_draw]
    if not subset:return
    # Draw one row per terminal descendant; node appears at the center of its leaves.
    subset_ids={n['node_id'] for n in subset}
    child_ids={n['node_id']:[c['node_id'] for c in n['children'] if c['node_id'] in subset_ids] for n in subset}
    finals=[n['node_id'] for n in subset if not child_ids[n['node_id']]]
    ymin={nid:i for i,nid in enumerate(finals)}
    def y(nid):
        if nid in ymin:return float(ymin[nid])
        return float(np.mean([y(t) for t in child_ids[nid]]))
    columns=max(n['depth']-root['depth'] for n in subset)+1
    fig,ax=plt.subplots(figsize=(max(13,4.6*columns),max(5,0.46*len(finals)+2.5)))
    palette=['#164c78','#287d91','#6b5da9','#af7a37','#437e5b']
    pos={}
    for n in subset:
        d=n['depth']-root['depth'];yy=y(n['node_id']);x=float(d)*4.8
        pos[n['node_id']]=(x,yy)
        boxtext=(f"{n['node_id']}  {n['provisional_data_label'][:49]}\n"
                 f"{n['term_count']} phrases · {n['patent_support']} patent units")
        ax.text(x,yy,boxtext,fontsize=7.6,color=('white' if not n['residual'] else '#212936'),
            va='center',ha='left',bbox=dict(boxstyle='round,pad=.40',
            facecolor=(palette[d%len(palette)] if not n['residual'] else '#dedfe3'),
            edgecolor='white',alpha=.98))
    for n in subset:
        if n['parent_id'] in pos:
            px,py=pos[n['parent_id']];cx,cy=pos[n['node_id']]
            ax.plot([px+2.7,cx-.1],[py,cy],lw=1.1,color='#8b97a6',alpha=.65,zorder=0)
    ax.set_xlim(-.25,4.8*(columns-1)+3.9)
    ax.set_ylim(len(finals)-.2,-1.3);ax.axis('off')
    ax.set_title(f'{root_id}: nested Leiden hierarchy — exact patent phrases, not verified technology names',
                 fontsize=11,loc='left',pad=14)
    fig.tight_layout()
    fig.savefig(FIG/(outname+'.png'),dpi=220,bbox_inches='tight')
    if SETTINGS['SAVE_VECTOR_FIGURES']:fig.savefig(FIG/(outname+'.svg'),bbox_inches='tight')
    plt.close(fig)
    atomic_csv(pd.DataFrame([{'node_id':n['node_id'],'parent_id':n['parent_id'],
       'depth':n['depth'],'y_layout':y(n['node_id']),
       'term_count':n['term_count'],'patent_units':n['patent_support'],
       'label':n['provisional_data_label'],'is_residual':n['residual']} for n in subset]),
       FIG/(outname+'_SOURCE_DATA.csv'))

render_branch('ROOT','FIG_04_ROOT_HIERARCHY',max_depth_to_draw=1)
for ch in NODE_RESULTS['ROOT']['children']:
    if ch['residual']:continue
    render_branch(ch['node_id'],f'FIG_05_DETAIL_{ch["node_id"]}',max_depth_to_draw=2)

# Plot distribution of leaf patent support and ROOT-to-leaf hierarchy counts.
if not leaf_summary_df.empty:
    display_df=leaf_summary_df.sort_values('supporting_patent_units',ascending=False).head(35)
    fig,ax=plt.subplots(figsize=(11,max(5,0.30*len(display_df)+1)))
    ax.barh(display_df.leaf_id[::-1],display_df.supporting_patent_units[::-1],color='#247f91')
    ax.set(xlabel='Patent units containing at least one leaf phrase',
           title='Non-exclusive patent support for terminal candidate groups')
    ax.grid(axis='x',alpha=.15);fig.tight_layout()
    fig.savefig(FIG/'FIG_06_LEAF_PATENT_SUPPORT.png',dpi=220,bbox_inches='tight')
    fig.savefig(FIG/'FIG_06_LEAF_PATENT_SUPPORT.svg',bbox_inches='tight');plt.close(fig)
    atomic_csv(display_df,FIG/'FIG_06_LEAF_PATENT_SUPPORT_SOURCE_DATA.csv')
say('[FIGURES] complete. Every figure has a source CSV; detailed tree pages are separate.')

# %% [markdown]
# ## 10. Manuscript-ready audit, references and **handoff ZIP for ChatGPT**

# %%
RREF=[
 {'id':'Traag2019','authors':['Traag, V. A.','Waltman, L.','van Eck, N. J.'],
  'year':'2019','title':'From Louvain to Leiden: guaranteeing well-connected communities',
  'journal':'Scientific Reports','volume':'9','pages':'5233','doi':'10.1038/s41598-019-41695-z'},
 {'id':'Reichardt2006','authors':['Reichardt, J.','Bornholdt, S.'],
  'year':'2006','title':'Statistical mechanics of community detection',
  'journal':'Physical Review E','volume':'74','pages':'016110','doi':'10.1103/PhysRevE.74.016110'},
 {'id':'Fortunato2007','authors':['Fortunato, S.','Barthélemy, M.'],
  'year':'2007','title':'Resolution limit in community detection',
  'journal':'Proceedings of the National Academy of Sciences','volume':'104',
  'pages':'36-41','doi':'10.1073/pnas.0605965104'},
 {'id':'Hubert1985','authors':['Hubert, L.','Arabie, P.'],
  'year':'1985','title':'Comparing partitions',
  'journal':'Journal of Classification','volume':'2','pages':'193-218',
  'doi':'10.1007/BF01908075'},
 {'id':'Lancichinetti2012','authors':['Lancichinetti, A.','Fortunato, S.'],
  'year':'2012','title':'Consensus clustering in complex networks',
  'journal':'Scientific Reports','volume':'2','pages':'336','doi':'10.1038/srep00336'},
 {'id':'Newman2006','authors':['Newman, M. E. J.'],
  'year':'2006','title':'Modularity and community structure in networks',
  'journal':'Proceedings of the National Academy of Sciences','volume':'103',
  'pages':'8577-8582','doi':'10.1073/pnas.0601602103'}]
ris=[]
for ref in RREF:
    ris.append('TY  - JOUR')
    ris.extend('AU  - '+a for a in ref['authors'])
    ris.extend([f'PY  - {ref["year"]}',f'TI  - {ref["title"]}',f'JO  - {ref["journal"]}',
      f'VL  - {ref["volume"]}',f'SP  - {ref["pages"]}',f'DO  - {ref["doi"]}',
      f'ID  - {ref["id"]}','ER  - ',''])
(HAND/'METHOD_REFERENCES.ris').write_text('\n'.join(ris),encoding='utf-8')
atomic_json(HAND/'METHOD_REFERENCES.json',RREF)

selected_splits=[n for n in NODE_RESULTS.values() if n['split_accepted']]
nonresid=[n for n in leaves if not n['residual']]
source_count=len(DOCS)
root_selected=NODE_RESULTS['ROOT']
root_best=next((c for c in root_selected['candidate_gamma_metrics']
               if c['gamma']==root_selected.get('selected_gamma')),None)
FACTS={
 'dataset_source':'Lens','collection_date':'2026-09-14',
 'retrieval_expression_user_reported':'Circular economy',
 'prior_run_identifier':SOURCE_METADATA.get('run_id'),
 'analytical_patent_units':source_count,
 'active_network_terms':G.vcount(),'weighted_graph_edges':G.ecount(),
 'connected_components':len(CC),'largest_connected_component_terms':max(component_sizes),
 'number_of_tested_gamma_root':len(root_scan),
 'original_archived_leiden_ROOT_metrics':(RAW_AUDIT.to_dict(orient='records') if RAW_AUDIT is not None else []),
 'optimized_ROOT_gamma':root_selected.get('selected_gamma'),
 'optimized_ROOT_decision':root_selected['stop_reason'],
 'optimized_ROOT_best_candidate_metrics':root_best,
 'execution_only_node_limit':RUNTIME_MAX_NODES,
 'original_model_config_max_nodes':SETTINGS['MAX_NODES'],
 'recursion_complete':not bool(queue),
 'checkpointed_nodes_reused':reused_nodes,
 'new_nodes_evaluated_in_final_pass':new_nodes,
 'total_hierarchy_nodes':len(NODE_RESULTS),
 'accepted_parent_splits':len(selected_splits),
 'total_terminal_nodes':len(leaves),
 'nonresidual_terminal_candidate_leaves':len(nonresid),
 'residual_terminal_nodes':sum(n['residual'] for n in leaves),
 'patent_units_with_any_nonresidual_leaf_phrase':int(sum(primary_df.primary_leaf_id!='UNMAPPED')),
 'patent_units_with_primary_ties':int(sum(primary_df.ambiguous_max_hit_tie)),
 'patent_leaf_multiple_membership_rows':len(multiple_df),
 'accuracy_claim':'NONE: ARI measures partition stability, not external classification accuracy',
 'technology_labels':'provisional patent-phrase descriptions; no external expert validation performed',
 'classification_note':'A patent can support multiple leaves; primary membership is an argmax heuristic',
 'resolution_selection':'feasibility and repeatability; NOT maximum number of clusters',
 'no_retrieval_text_fraction_claims':True,
 'limitations_for_manuscript':[ 'Preexisting Lens export is reused without changing search criteria.',
  'Network derived from automatically extracted contiguous title/abstract phrases.',
  'Network pruning and retrieval choices affect detected groups.',
  'Document bootstrap uses original topology but reweights co-occurrence edges.',
  'Smaller child branches are screened using seed and gamma stability; document bootstrap ranking is ROOT-only.',
  'Threshold values are study-specific screens, not universally validated standards.']}
atomic_json(HAND/'MANUSCRIPT_FACTS_VERIFIED_FROM_OUTPUTS.json',FACTS)
# Human-readable multi-sheet companion; original CSV files remain the analysis authority.
with pd.ExcelWriter(HAND/'PAPER_TABLES_ALL_SUMMARIES.xlsx',engine='openpyxl') as workbook:
    sheets={
       'Results Facts':pd.DataFrame([(k,str(v)[:30000]) for k,v in FACTS.items()],columns=['metric','value']),
       'ROOT Gamma Grid':root_scan,
       'All Node Decisions':NODE_METRICS,
       'Every Parameter Gate':SCANS,
       'Leaf Candidates':leaf_summary_df,
       'Patent Examples':pd.DataFrame(patent_examples),
       'CPC Evidence':pd.DataFrame(cpc_rows),
       'ROOT Bootstrap':BOOTSTRAPS,
       'Cap ARI Sensitivity':pd.DataFrame(GATE_COUNTERFACTUAL)}
    if RAW_AUDIT is not None:sheets['Original Leiden ROOT']=RAW_AUDIT
    for title,data in sheets.items():
        if len(data.columns)==0:continue
        data.to_excel(workbook,sheet_name=title,index=False)
REPORT=f'''# Manuscript handoff: optimized nested Leiden circular-economy taxonomy

Run ID: {RUN_ID}
Archived run ID: {SOURCE_METADATA.get('run_id','unavailable')}
Lens data collection: 14 September 2026 (user-reported).

## Main outcomes
- Source document units: {len(DOCS):,}
- Weighted network: {G.vcount():,} connected term vertices and {G.ecount():,} edges
- Original connected components: {len(CC)} (largest {max(component_sizes):,} phrases)
- ROOT selected gamma: {root_selected.get('selected_gamma')}
- ROOT stop/acceptance reason: {root_selected['stop_reason']}
- Hierarchy nodes: {len(NODE_RESULTS)}, accepted splits: {len(selected_splits)}
- Terminal non-residual groups: {len(nonresid)}; residual terminal nodes: {sum(n['residual'] for n in leaves)}
- Patent units matching at least one non-residual leaf phrase: {sum(primary_df.primary_leaf_id!='UNMAPPED'):,}

## Execution-only continuation from the 200-node guard
The 200-node stop was a computational guard, not an acceptance condition. The continuation
uses the same RUN_ID and scientific settings; completed independent node checkpoints are
replayed without repeating their Leiden partitions. The execution-only increased node
limit is recorded in 01_selection_audit/EXECUTION_CAP_EXTENSION.json.

## Importantly
The ROOT gamma was **not** selected to maximize the number of communities.
All candidate gamma values, rejection criteria, seeds, ARI measurements, perturbation results,
and node decisions are saved as CSV/JSON. Some candidate branches can remain unsplit;
never write them up as accepted technology leaves if no gamma passes the checks.
These are data-driven term-network communities, not independently certified industrial technologies.
Do not claim that a fraction of exported titles or abstracts must contain the literal search phrase.
No expert judgments or personal information enter this computational analysis.

## Reproduction and scientific rationale
- Traag et al. (2019): Leiden algorithm and connected-community guarantees.
- Reichardt and Bornholdt (2006): resolution-adjustable configuration null model.
- Fortunato and Barthélemy (2007): modularity resolution limitations.
- Hubert and Arabie (1985): corrected-for-chance comparison of partitions (ARI).
- Lancichinetti and Fortunato (2012): repeated partitions and consensus/stability concepts.

All screening cutoffs (including 0.55 ARI) are **declared analyst choices**.
They are not claimed to be conventional universal benchmarks.
We report the full gamma grid, random-seed repeatability, neighboring-gamma continuity,
weighted conductance, residual fraction, patent support, and (ROOT) document bootstrap.
Generalized modularity at different gamma values is **not compared directly** to select gamma.

## Important files
- 01_selection_audit/EVERY_GAMMA_EVERY_GATE.csv: ALL screened parameter values, failures and choice metadata\n- 01_selection_audit/COUNTERFACTUAL_GATE_SENSITIVITY_NOT_USED_FOR_SELECTION.csv: test alternate ARI, cap and remainder assumptions WITHOUT modifying chosen tree
- 01_selection_audit/EVERY_RANDOM_SEED_PARTITION.csv: every replicate, its quality and runtime
- 01_selection_audit/ALL_PAIRWISE_ARI.csv: all repeated-run ARIs
- 01_selection_audit/ALL_NODE_DECISIONS.csv: each node, parent, chosen gamma and stop reason
- 03_taxonomy/FULL_HIERARCHY_NODE_TABLE.csv: complete hierarchy and phrase-based labels
- 03_taxonomy/TECHNOLOGY_TREE_READABLE.txt: plain-text indented hierarchy
- 03_taxonomy/LEAF_TECHNOLOGY_CANDIDATES.csv: patent support by terminal candidate group
- 04_patent_evidence/ALL_EXACT_KEYPHRASES_EVERY_LEVEL.csv: every term and every level
- 04_patent_evidence/PATENT_PRIMARY_HEURISTIC_ASSIGNMENT.csv: primary membership
- 04_patent_evidence/PATENT_MULTIPLE_LEAF_MEMBERSHIPS.csv: all overlaps
- 04_patent_evidence/REPRESENTATIVE_PATENTS_PER_LEAF.csv: actual example patents
- 04_patent_evidence/CPC_SUBCLASS_PROFILES_PER_LEAF.csv: subclass supporting evidence
- 05_figures: publication-ready SVG/PNG plus exact figure-source CSVs
- 06_paper_handoff/MANUSCRIPT_FACTS_VERIFIED_FROM_OUTPUTS.json: manuscript fact sheet
- 06_paper_handoff/METHOD_REFERENCES.ris: verified references for EndNote
- 07_logs: cumulative printed evidence and progress log
'''
(HAND/'PAPER_WRITING_README.md').write_text(REPORT,encoding='utf-8')
METHODS_DRAFT=r'''# Methods-only material for the revised manuscript (no empirical findings)

The analytical unit is a patent-family representative inherited from the original Lens-processing
pipeline. The previously constructed binary document–phrase incidence matrix and weighted
co-occurrence graph are used as fixed inputs. For patent unit d and literal phrase i, X_di = 1
if the phrase is retained for that document and 0 otherwise. The co-occurrence count is
c_ij = Σ_d X_di X_dj and the graph-edge weight is
w_ij = [c_ij / sqrt(f_i f_j)] log(1+c_ij), where f_i = Σ_d X_di.
No language extraction, normalization, search rerun or edge filtering is performed in the
present parameter-selection phase.

Community detection uses the Leiden algorithm with the Reichardt–Bornholdt configuration
null model. For a resolution parameter γ, its normalized generalized modularity is
Q_γ = (1/2m) Σ_ij [A_ij − γ k_i k_j/(2m)] 𝟙(g_i=g_j).
Here A_ij is the observed edge weight, k_i its weighted degree, 2m is the total vertex
strength, and g_i denotes a term's assigned community. The improvement over the single-
community partition is computed only at the same γ. Generalized modularity is not treated
as a directly comparable objective value across different resolutions.

A predeclared grid of γ values is fitted to the root network. At each γ, independent
seeded partitions are calculated. Their repeatability is evaluated with the adjusted Rand
index (ARI), separately over all vertices and over the largest connected component to
avoid exaggerating stability through disconnected small components. For each candidate
γ, its adjacent-resolution stability is computed by comparing partitions produced at
neighboring tested γ values. The minimum information requirements comprise child-term
size, patent-unit support, parent size, residual-term coverage, and positive improvement
against the one-community baseline. Each is audited as a separate acceptance condition.
These thresholds are explicit research-design choices; none is described as a universal
cutoff supplied by the Leiden or ARI literature.

Feasible candidate resolutions are ranked lexicographically by neighboring-resolution
agreement, repeated-seed agreement, smaller residual fraction, lower median weighted
conductance, and finally γ. The rank does not use the number of discovered communities.
For the root decision, document-level bootstrap agreement is the primary continuous
ranking criterion for feasible resolutions. Bootstrap samples test the stability of
candidate partitions, with network topology fixed and edge weights recalculated from
the resampled document–phrase incidence matrix. Successful root splitting triggers
recursion on the induced subgraphs of its eligible child groups using a bounded local
resolution grid. Invalid small communities form a recorded residual terminal node.
Every run, rejection, bootstrap comparison and final parent–child relationship is written
to an immutable checkpoint with the source-network hash and configuration. Patent support
is non-exclusive across terminal term groups; the additional primary assignment is an
explicit maximum-term-hit heuristic. Provisional labels consist exclusively of actual
patent phrases and do not purport to be externally validated technology classes.

Sources: Reichardt and Bornholdt (2006); Newman (2006); Fortunato and Barthélemy (2007);
Hubert and Arabie (1985); Lancichinetti and Fortunato (2012); Traag et al. (2019).
Full bibliographic records are in METHOD_REFERENCES.ris.
'''
(HAND/'METHODS_ONLY_FOR_ARTICLE.md').write_text(METHODS_DRAFT,encoding='utf-8')
say(REPORT)

# Reproducibility metadata and complete output checksums (before adding final zips).
version_keys=['numpy','pandas','scipy','scikit-learn','python-igraph','leidenalg',
               'matplotlib','plotly','networkx']
versions={}
for k in version_keys:
    try:versions[k]=importlib.metadata.version(k)
    except importlib.metadata.PackageNotFoundError:versions[k]='not installed'
atomic_json(OUT/'REPRODUCIBILITY_PROVENANCE.json',{
 'run_id':RUN_ID,'source_fingerprint':SOURCE_FINGERPRINT,
 'input_provenance':input_manifest,'python':sys.version,
 'versions':versions,'platform':platform.platform(),
 'created_utc':datetime.now(timezone.utc).isoformat(),
 'settings':SETTINGS,
 'execution_only_node_limit':RUNTIME_MAX_NODES,
 'original_model_config_max_nodes':SETTINGS['MAX_NODES'],
 'execution_cap_audit_file':'01_selection_audit/EXECUTION_CAP_EXTENSION.json',
 'method_references':RREF,
 'caveats':FACTS['limitations_for_manuscript']})

# Curate a small self-contained upload ZIP so the researcher can share it to
# ChatGPT for manuscript rewriting, without moving the full Drive again.
HANDOFF_ZIP=OUT/'SEND_TO_CHATGPT_FOR_MANUSCRIPT_REWRITE.zip'
ALLOWED_PREFIXES=['01_selection_audit/','03_taxonomy/','04_patent_evidence/',
                  '05_figures/','06_paper_handoff/']
with zipfile.ZipFile(str(HANDOFF_ZIP)+'.partial','w',compression=zipfile.ZIP_DEFLATED,
                     compresslevel=5,allowZip64=True) as z:
    for p in sorted(OUT.rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(OUT).as_posix()
        if rel.startswith(tuple(ALLOWED_PREFIXES)) or rel=='REPRODUCIBILITY_PROVENANCE.json':
            z.write(p,rel)
    # Original real-data evidence, not just computed summaries.
    for rel in relative_needed:
        if rel=='02_tables/analysis_patent_families.csv' and not SETTINGS['INCLUDE_DOCUMENT_METADATA_IN_PAPER_PACKAGE']:
            continue
        z.write(INPUT_BASE/rel,'00_ORIGINAL_RUN_EVIDENCE/'+rel)
    for rel in ['04_taxonomy/hierarchical_community_metrics.csv','04_taxonomy/leiden_restart_stability_diagnostics.csv',
                'RUN_CONFIGURATION_AND_PROVENANCE.json']:
        p=INPUT_BASE/rel
        if p.is_file():z.write(p,'00_ORIGINAL_RUN_EVIDENCE/'+rel)
Path(str(HANDOFF_ZIP)+'.partial').replace(HANDOFF_ZIP)
say('PAPER HANDOFF ZIP:',HANDOFF_ZIP,'bytes',HANDOFF_ZIP.stat().st_size)

# Complete optional archive (exclude input cache and any zip already being built).
if SETTINGS['CREATE_FULL_ARCHIVE']:
    allzip=OUT/'FULL_OPTIMIZER_AUDIT_AND_CHECKPOINTS.zip'
    with zipfile.ZipFile(str(allzip)+'.partial','w',compression=zipfile.ZIP_DEFLATED,
                          compresslevel=4,allowZip64=True) as z:
        for p in sorted(OUT.rglob('*')):
            if not p.is_file() or p==allzip or p==HANDOFF_ZIP or CACHE in p.parents:continue
            z.write(p,p.relative_to(OUT))
    Path(str(allzip)+'.partial').replace(allzip)
    say('FULL CHECKPOINT ARCHIVE:',allzip,'bytes',allzip.stat().st_size)

inventory=[]
for p in sorted(OUT.rglob('*')):
    if not p.is_file():continue
    if p.name.endswith('.partial'):continue
    if p.name=='FINAL_OUTPUT_INVENTORY_SHA256.csv':continue
    inventory.append({'relative_path':p.relative_to(OUT).as_posix(),
                      'bytes':p.stat().st_size,'sha256':sha256_file(p)})
atomic_csv(pd.DataFrame(inventory),OUT/'FINAL_OUTPUT_INVENTORY_SHA256.csv')
say('OUTPUT FILE COUNT:',len(inventory))
say('\n'+'='*100+'\nANALYSIS COMPLETED.')
say('TO SEND ME FOR THE NEW PAPER:',HANDOFF_ZIP)
say('DIRECTORY (restart-safe):',OUT)
say('No text retrieval, source cleaning or graph construction rerun.')
