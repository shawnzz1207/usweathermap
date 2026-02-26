import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor

# 【网页基础设置】
st.set_page_config(page_title="全美实时气候热力图", page_icon="🗺️", layout="wide")

st.title("🗺️ 全美实时气候热力图")
st.markdown("**数据来源**:[Open-Meteo 实时气象预报API](https://open-meteo.com) | **实时获取全美50州气温**")

# ==========================
# 🎨 新增：侧边栏自定义温度区间
# ==========================
st.sidebar.header("🎨 自定义温度色带")
st.sidebar.markdown("请拖动滑块，设定不同颜色代表的**摄氏度(℃)**：")

# 提供5个滑块供用户自定义，并设置合理的默认值和调节范围
t1 = st.sidebar.slider("🔵 深蓝色 (极寒下限)", min_value=-40, max_value=0, value=-10)
t2 = st.sidebar.slider("🟦 浅蓝色 (寒冷)", min_value=-20, max_value=15, value=0)
t3 = st.sidebar.slider("🟨 浅黄色 (适宜)", min_value=-10, max_value=25, value=10)
t4 = st.sidebar.slider("🟧 橙红色 (温暖)", min_value=0, max_value=35, value=20)
t5 = st.sidebar.slider("🔴 深红色 (酷热上限)", min_value=15, max_value=50, value=30)

# 为了防止用户错误设置导致程序崩溃（比如把浅蓝设置得比深蓝还低），我们在后台自动为温度排序
temps = sorted([t1, t2, t3, t4, t5])
min_t, max_t = temps[0], temps[4]

# 避免最大值和最小值相等导致除以 0 的错误
if max_t == min_t:
    max_t = min_t + 1

# 核心算法：将真实的温度转化为 Plotly 能够识别的 0.0 ~ 1.0 比例
dynamic_color_scale = [[0.0, "darkblue"],  # 强制对应 min_t
                       [(temps[1] - min_t) / (max_t - min_t), "dodgerblue"],  # 按比例换算浅蓝位置
                       [(temps[2] - min_t) / (max_t - min_t), "lightyellow"],  # 按比例换算浅黄位置
                       [(temps[3] - min_t) / (max_t - min_t), "tomato"],
                       # 按比例换算橙红位置[1.0, "darkred"]                                        # 强制对应 max_t
                       ]

# ==========================
# 🌍 数据拉取与缓存处理
# ==========================
state_coords = {
    'AL': [32.8066, -86.7911], 'AK': [61.3707, -152.4044], 'AZ': [33.7298, -111.4312],
    'AR': [34.9697, -92.3731], 'CA': [36.1162, -119.6816], 'CO': [39.0598, -105.3111],
    'CT': [41.5978, -72.7554], 'DE': [39.3185, -75.5071], 'FL': [27.7663, -81.6868],
    'GA': [33.0406, -83.6431], 'HI': [21.0943, -157.4983], 'ID': [44.2405, -114.4788],
    'IL': [40.3495, -88.9861], 'IN': [39.8494, -86.2583], 'IA': [42.0115, -93.2105],
    'KS': [38.5266, -96.7265], 'KY': [37.6681, -84.6701], 'LA': [31.1695, -91.8678],
    'ME': [44.6939, -69.3819], 'MD': [39.0639, -76.8021], 'MA': [42.2302, -71.5301],
    'MI': [43.3266, -84.5361], 'MN': [45.6945, -93.9002], 'MS': [32.7416, -89.6787],
    'MO': [38.4561, -92.2884], 'MT': [46.9219, -110.4544], 'NE': [41.1254, -98.2681],
    'NV': [38.3135, -117.0554], 'NH': [43.7932, -71.5925], 'NJ': [40.2989, -74.5210],
    'NM': [34.8405, -106.2485], 'NY': [42.1657, -74.9481], 'NC': [35.6301, -79.8064],
    'ND': [47.5289, -99.7840], 'OH': [40.3888, -82.7649], 'OK': [35.5653, -96.9289],
    'OR': [44.5720, -122.0709], 'PA': [40.5908, -77.2098], 'RI': [41.6809, -71.5118],
    'SC': [33.8569, -80.9450], 'SD': [44.2998, -99.4388], 'TN': [35.7478, -86.6923],
    'TX': [31.0545, -97.5635], 'UT': [40.1500, -111.8624], 'VT': [44.0459, -72.7107],
    'VA': [37.7693, -78.1699], 'WA': [47.4009, -121.4905], 'WV': [38.4912, -80.9545],
    'WI': [44.2685, -89.6165], 'WY': [42.7560, -107.3025]
}


@st.cache_data(ttl=600)
def get_weather_data():
    def fetch_weather(state, coords):
        url = f"https://api.open-meteo.com/v1/forecast?latitude={coords[0]}&longitude={coords[1]}&current_weather=true"
        try:
            res = requests.get(url, timeout=5).json()
            temp = res.get("current_weather", {}).get("temperature", None)
            return {"State": state, "Temperature (°C)": temp}
        except Exception:
            return {"State": state, "Temperature (°C)": None}

    weather_data = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_weather, state, coords) for state, coords in state_coords.items()]
        for future in futures:
            weather_data.append(future.result())

    df = pd.DataFrame(weather_data)
    return df.dropna(subset=["Temperature (°C)"])


with st.spinner('卫星正在接收全美气象数据，请稍候...'):
    df = get_weather_data()

# ==========================
# 📊 渲染热力图
# ==========================
if not df.empty:
    fig = px.choropleth(
        df,
        locations="State",
        locationmode="USA-states",
        color="Temperature (°C)",
        scope="usa",
        color_continuous_scale=dynamic_color_scale,  # 载入刚才动态计算出来的色带配置
        range_color=[min_t, max_t]  # 载入用户设置的下限和上限
    )

    # 增加图表高度，使其在宽屏下更美观
    fig.update_layout(height=600, margin={"r": 0, "t": 0, "l": 0, "b": 0})

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📝 查看或下载各州具体温度数据"):
        st.dataframe(df.sort_values(by="Temperature (°C)", ascending=False), use_container_width=True)
else:
    st.error("数据获取失败，请检查网络。")