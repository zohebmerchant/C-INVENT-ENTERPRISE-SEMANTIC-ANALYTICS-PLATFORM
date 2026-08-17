"""C INVENT visual system and stable single-document navigation."""
import streamlit as st

NAVY='#0B1F36'; NAVY2='#102B49'; TEAL='#0A8FA3'; TEAL2='#087B8C'; CANVAS='#F4F7FA'; PANEL='#FFFFFF'; SLATE='#23364D'; SOFT='#6C7E91'; LINE='#DCE5ED'; GREEN='#168A58'; GREEN_LIGHT='#EAF8F1'; AMBER='#C77A19'; AMBER_LIGHT='#FFF6E6'; RED='#B84B45'
NAV_GROUPS=[('ONBOARD',[('Data Onboarding','⇧'),('Databricks Discovery','⌘')]),('MODEL',[('AI Analysis','✦'),('Semantic Intelligence','◈'),('Business Model','◇'),('QA Validation','✓')]),('ANALYZE',[('Analytics','▥'),('Ask AI','▤'),('Genie AI','✧')]),('GOVERN',[('Security Center','◇'),('Connectors','↗'),('Audit & Policies','◷'),('Deployment Verification','✓')])]

def inject_base_css():
    st.markdown(f'''<style>
    #MainMenu,footer{{visibility:hidden}} html,body,[class*="css"]{{font-family:Inter,system-ui,sans-serif}} .stApp{{background:{CANVAS};color:{SLATE}}}
    .block-container{{max-width:1400px;padding:1.4rem 2rem 3rem}}
    [data-testid="stHeader"]{{background:#fff;border-bottom:1px solid {LINE}}}
    [data-testid="stSidebar"]{{background:{NAVY}!important;border-right:1px solid rgba(255,255,255,.08);min-width:255px!important}}
    [data-testid="stSidebar"]>div:first-child{{padding:.12rem .42rem .25rem!important}}
    [data-testid="stSidebarContent"]{{padding:.05rem .08rem 5.6rem!important;overflow-y:auto!important;scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.22) transparent}}
    [data-testid="stSidebar"] .cinvent-identity-card{{position:fixed;left:10px;bottom:10px;width:235px;box-sizing:border-box;z-index:1000;background:#142B45;border:1px solid rgba(255,255,255,.14);border-radius:12px;padding:9px 10px;box-shadow:0 10px 28px rgba(0,0,0,.24)}}
    [data-testid="stSidebar"] .cinvent-identity-row{{display:flex;align-items:center;gap:9px}}
    [data-testid="stSidebar"] .cinvent-identity-avatar{{width:32px;height:32px;min-width:32px;border-radius:50%;background:linear-gradient(135deg,#0A8FA3,#0875D1);display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;font-weight:900}}
    [data-testid="stSidebar"] .cinvent-identity-name{{color:#fff;font-size:10.5px;font-weight:800;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    [data-testid="stSidebar"] .cinvent-identity-role{{color:#57D1D7;font-size:9px;font-weight:800;margin-top:2px}}
    [data-testid="stSidebar"] .cinvent-identity-email{{color:#8FA5B9;font-size:7.5px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    [data-testid="stSidebarUserContent"]{{padding-bottom:.25rem!important}}
    [data-testid="stSidebar"] [data-testid="stButton"]{{width:100%;margin:0!important;padding:0!important}}
    [data-testid="stSidebar"] [data-testid="stButton"] button{{width:100%!important;min-height:27px!important;height:27px!important;border:1px solid transparent!important;border-radius:9px!important;background:transparent!important;color:#C9D7E5!important;box-shadow:none!important;justify-content:flex-start!important;text-align:left!important;padding:.06rem .45rem!important;font-size:11px!important;font-weight:600!important}}
    [data-testid="stSidebar"] [data-testid="stButton"] button:hover{{background:rgba(255,255,255,.08)!important;color:#fff!important}}
    [data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"]{{background:{TEAL}!important;border-color:{TEAL}!important;color:#fff!important}}
    .invent-brand{{display:flex;align-items:center;gap:8px;padding:0 4px 5px;margin:0 0 3px;border-bottom:1px solid rgba(255,255,255,.11)}}
    .invent-logo{{width:28px;height:28px;min-width:28px;border-radius:10px;background:linear-gradient(135deg,#0A8FA3,#0875D1);display:flex;align-items:center;justify-content:center;color:#fff;font-weight:900;font-size:16px;box-shadow:0 7px 18px rgba(0,0,0,.22)}}
    .invent-brand-name{{color:#fff;font-weight:800;font-size:13px;line-height:1}} .invent-brand-sub{{color:#8FA5B9;font-size:8px;margin-top:3px;letter-spacing:.25px}}
    .invent-nav-heading{{color:#6F879B;font-size:7.5px;font-weight:900;letter-spacing:1.5px;margin:4px 5px 1px;line-height:11px}}
    .platform-topbar{{background:#fff;border:1px solid {LINE};border-radius:13px;padding:17px 22px;margin-bottom:17px;box-shadow:0 2px 8px rgba(16,42,73,.035)}}
    .platform-topbar h1{{font-size:25px;font-weight:800;color:{NAVY};margin:0}} .platform-topbar-sub{{font-size:12.5px;color:{SOFT};margin-top:4px}}
    .platform-card-title{{font-size:16px;font-weight:800;color:{NAVY};margin-bottom:2px}} .platform-card-sub{{font-size:12px;color:{SOFT};margin-bottom:10px}}
    [data-testid="stMetric"]{{background:#fff;border:1px solid {LINE};border-radius:11px;padding:14px 16px}} [data-testid="stMetricLabel"]{{color:{SOFT}!important;font-size:10px!important;font-weight:800!important;text-transform:uppercase;letter-spacing:.45px}} [data-testid="stMetricValue"]{{color:{NAVY}!important;font-size:24px!important;font-weight:800!important}}
    .platform-tag{{display:inline-block;padding:4px 9px;border-radius:999px;font-size:10px;font-weight:800}} .platform-tag.ok{{background:{GREEN_LIGHT};color:{GREEN}}} .platform-tag.warn{{background:{AMBER_LIGHT};color:{AMBER}}} .platform-tag.ai{{background:#EDF5FF;color:#0875D1}}
    .platform-banner{{background:{AMBER_LIGHT};border:1px solid #F0D7A8;border-radius:9px;padding:10px 13px;font-size:12px;color:#76571E;margin-bottom:13px}} .platform-banner.info{{background:#EDF7FB;border-color:#CBE4EF;color:#315E78}} .platform-banner.ok{{background:{GREEN_LIGHT};border-color:#CFEBDD;color:#205C43}}
    .stButton>button{{border-radius:8px!important;min-height:39px;font-weight:700}} .stButton>button[kind="primary"]{{background:{TEAL}!important;border-color:{TEAL}!important;color:#fff!important}} .stButton>button[kind="primary"]:hover{{background:{TEAL2}!important;border-color:{TEAL2}!important}}
    .stTextInput input,.stTextArea textarea,.stSelectbox div[data-baseweb="select"]>div{{border-radius:8px!important}}
    .home-hero{{background:linear-gradient(135deg,#08223C,#0B4C67);border-radius:18px;padding:44px 42px;color:#fff;margin-bottom:17px;box-shadow:0 18px 45px rgba(8,34,60,.13)}} .home-hero .eyebrow{{color:#57D1D7;font-size:10px;font-weight:900;letter-spacing:1.8px}} .home-hero h1{{font-size:40px;line-height:1.08;margin:10px 0 12px;color:#fff}} .home-hero p{{max-width:760px;color:#B9D0DF;font-size:14px;line-height:1.65}}
    .c-card{{background:#fff;border:1px solid {LINE};border-radius:12px;padding:16px;height:100%}} .c-card h3{{font-size:14px;margin:0 0 6px;color:{NAVY}}} .c-card p{{font-size:11px;color:{SOFT};margin:0;line-height:1.55}}
    .flow{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:12px 0 18px}} .flow span{{padding:7px 10px;background:#fff;border:1px solid {LINE};border-radius:999px;font-size:10px;font-weight:800;color:#53687C}} .flow span.active{{background:#EAF7F8;border-color:#BDE0E4;color:{TEAL}}}
    </style>''',unsafe_allow_html=True)

def navigate_to(page_name:str):
    valid={'Home'}|{n for _,pages in NAV_GROUPS for n,_ in pages}
    if page_name not in valid: page_name='Home'
    st.session_state['_invent_current_page']=page_name
    st.session_state['_invent_internal_navigation']=True
    st.rerun()

def render_sidebar_brand():
    with st.sidebar:
        st.markdown('''<div class="invent-brand"><div class="invent-logo">C</div><div><div class="invent-brand-name">C INVENT</div><div class="invent-brand-sub">Enterprise Semantic Analytics Platform</div></div></div>''',unsafe_allow_html=True)

def render_sidebar_navigation():
    current=st.session_state.get('_invent_current_page','Home')
    with st.sidebar:
        if st.button('⌂  Home',key='nav_home',use_container_width=True,type='primary' if current=='Home' else 'secondary'): navigate_to('Home')
        for heading,pages in NAV_GROUPS:
            st.markdown(f'<div class="invent-nav-heading">{heading}</div>',unsafe_allow_html=True)
            for page,icon in pages:
                if st.button(f'{icon}  {page}',key='nav_'+page.lower().replace(' ','_'),use_container_width=True,type='primary' if current==page else 'secondary'): navigate_to(page)

        # Signed-in identity stays at the bottom of the C INVENT navigation.
        try:
            from auth import current_user
            user = current_user()
        except Exception:
            user = None

        if user:
            email = user.get('email', '')
            role = user.get('role', '')
            local_part = email.split('@', 1)[0] if '@' in email else email
            display_name = ' '.join(part.capitalize() for part in local_part.replace('-', ' ').replace('_', ' ').split())
            if not display_name:
                display_name = 'C INVENT User'
            initials = ''.join(part[0].upper() for part in display_name.split()[:2]) or 'CI'
            st.markdown(
                f'''<div class="cinvent-identity-card">
                    <div class="cinvent-identity-row">
                        <div class="cinvent-identity-avatar">{initials}</div>
                        <div style="min-width:0;flex:1">
                            <div class="cinvent-identity-name">{display_name}</div>
                            <div class="cinvent-identity-role">{role}</div>
                            <div class="cinvent-identity-email">{email}</div>
                        </div>
                    </div>
                </div>''',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="cinvent-identity-card"><div class="cinvent-identity-name">C INVENT</div></div>', unsafe_allow_html=True)

def page_header(title,subtitle): st.markdown(f'<div class="platform-topbar"><h1>{title}</h1><div class="platform-topbar-sub">{subtitle}</div></div>',unsafe_allow_html=True)
def section_title(title,subtitle=''):
    subtitle_html = f'<div class="platform-card-sub">{subtitle}</div>' if subtitle else ""
    html = f'<div class="platform-card-title">{title}</div>{subtitle_html}'
    st.markdown(html, unsafe_allow_html=True)
