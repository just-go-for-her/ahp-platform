import streamlit as st

st.title("📝 AHP 설문 조사 (Survey)")

st.warning("🚧 현재 설문 모듈은 개발 중입니다.")
st.markdown("""
친구분께서 멋진 설문 도구를 만들고 계십니다! 
완성되면 이곳에 연동될 예정입니다.

**향후 계획:**
- 웹 기반 실시간 쌍대비교 설문
- 응답 일관성(CR) 실시간 체크 기능
""")

# 나중에 친구분이 웹사이트를 다 만들면, 아래처럼 iframe으로 띄울 수도 있습니다.
# st.components.v1.iframe("친구의_설문사이트_URL", height=600)
