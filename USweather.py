import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from concurrent.futures import ThreadPoolExecutor

# 【网页基础设置】
st.set_page_config(page_title="全美实时气候热力图", page_icon="🗺️", layout="wide")

st.title("🗺️ 全美实时气候热力图 (支持滚轮缩放与城市测温)")
st.markdown(
    "**数据来源**:[Open-Meteo 实时气象预报](https://open-meteo.com) | **提示：请将鼠标放在地图上，使用滚轮放大查看细节**")

# ==========================
# 🎨 侧边栏控制面板
# ==========================
st.sidebar.header("🎨 控制面板")

# 【更新需求2】：城市图层控制开关 (默认设为 False 关闭)
show_cities = st.sidebar.toggle("🏙️ 叠加显示主要城市气温", value=False)
st.sidebar.markdown("---")

st.sidebar.markdown("拖动滑块，设定颜色代表的**摄氏度(℃)**：")

t1 = st.sidebar.slider("🔵 深蓝色 (极寒下限)", min_value=-40, max_value=0, value=-10)
t2 = st.sidebar.slider("🟦 浅蓝色 (寒冷)", min_value=-20, max_value=15, value=0)
t3 = st.sidebar.slider("🟨 浅黄色 (适宜)", min_value=-10, max_value=25, value=10)
t4 = st.sidebar.slider("🟧 橙红色 (温暖)", min_value=0, max_value=35, value=20)
t5 = st.sidebar.slider("🔴 深红色 (酷热上限)", min_value=15, max_value=50, value=30)

temps = sorted([t1, t2, t3, t4, t5])
min_t, max_t = temps[0], temps[4]
if max_t == min_t:
    max_t = min_t + 1

dynamic_color_scale = [[0.0, "darkblue"],
                       [(temps[1] - min_t) / (max_t - min_t), "dodgerblue"],
                       [(temps[2] - min_t) / (max_t - min_t), "lightyellow"],
                       [(temps[3] - min_t) / (max_t - min_t), "tomato"],
                       [1.0, "darkred"]
                       ]

# ==========================
# 🌍 数据字典 (50州 + 20大城市)
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

city_coords = {
    'New York': [40.7128, -74.0060], 'Los Angeles': [34.0522, -118.2437],
    'Chicago': [41.8781, -87.6298], 'Houston': [29.7604, -95.3698],
    'Phoenix': [33.4484, -112.0740], 'Philadelphia': [39.9526, -75.1652],
    'San Antonio': [29.4241, -98.4936], 'San Diego': [32.7157, -117.1611],
    'Dallas': [32.7767, -96.7970], 'San Jose': [37.3382, -121.8863],
    'Austin': [30.2672, -97.7431], 'Seattle': [47.6062, -122.3321],
    'Denver': [39.7392, -104.9903], 'Washington DC': [38.9072, -77.0369],
    'Boston': [42.3601, -71.0589], 'Las Vegas': [36.1699, -115.1398],
    'Miami': [25.7617, -80.1918], 'Atlanta': [33.7490, -84.3880],
    'Honolulu': [21.3069, -157.8583], 'Anchorage': [61.2181, -149.9003]
}


# ==========================
# 📡 异步拉取数据 (州 + 城市)
# ==========================
@st.cache_data(ttl=600)
def get_all_weather_data():
    def fetch_weather(name, coords, loc_type):
        url = f"https://api.open-meteo.com/v1/forecast?latitude={coords[0]}&longitude={coords[1]}&current_weather=true"
        try:
            res = requests.get(url, timeout=5).json()
            temp = res.get("current_weather", {}).get("temperature", None)
            return {"Name": name, "Lat": coords[0], "Lon": coords[1], "Temperature (°C)": temp, "Type": loc_type}
        except Exception:
            return {"Name": name, "Lat": coords[0], "Lon": coords[1], "Temperature (°C)": None, "Type": loc_type}

    results = []
    tasks = [(name, coords, "State") for name, coords in state_coords.items()] + \[(name, coords, "City") for
                                                                                   name, coords in city_coords.items()]

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(fetch_weather, t[0], t[1], t[2]) for t in tasks]
        for future in futures:
            results.append(future.result())

    df = pd.DataFrame(results).dropna(subset=["Temperature (°C)"])
    return df[df["Type"] == "State"], df[df["Type"] == "City"]


with st.spinner('卫星正在接收全美气象数据，包含各州与主要城市，请稍候...'):
    df_states, df_cities = get_all_weather_data()

# ==========================
# 📊 渲染多图层高级地图
# ==========================
if not df_states.empty:
    # 🌟 第一层：底层热力底图 (给各个州上色)
    fig = px.choropleth(
        df_states,
        locations="Name",
        locationmode="USA-states",
        color="Temperature (°C)",
        scope="usa",
        color_continuous_scale=dynamic_color_scale,
        range_color=[min_t, max_t],
        hover_name="Name"
    )

    # 🌟 第二层：州名简称文本 (强行贴在每个州的中心)
    fig.add_scattergeo(
        locations=df_states["Name"],
        locationmode="USA-states",
        text=df_states["Name"],
        mode="text",
        textfont=dict(color="rgba(255, 255, 255, 0.7)", size=12, family="Arial Black"),
        hoverinfo="skip",
        showlegend=False
    )

    # 🌟 第三层：主要城市坐标点与气温 (受侧边栏开关控制)
    if show_cities:
        df_cities["City_Label"] = df_cities["Name"] + ": " + df_cities["Temperature (°C)"].astype(str) + "℃"

        fig.add_scattergeo(
            lon=df_cities["Lon"],
            lat=df_cities["Lat"],
            text=df_cities["City_Label"],
            mode="markers+text",
            textposition="bottom center",
            marker=dict(size=7, color="black", line=dict(width=1.5, color="white")),
            textfont=dict(color="black", size=11, family="Arial Black"),
            name="主要城市",
            hoverinfo="text",
            showlegend=False  # 【更新需求1】：隐藏右上角多余的文字图例
        )

    # 【更新需求1】：优化界面边距，把 t:0 改成 t:40 防止UI重叠
    fig.update_layout(
        height=650,
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        dragmode="zoom"
    )

    # 给 st.plotly_chart 传入 config，强制开启滚轮缩放功能
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            'scrollZoom': True,
            'displayModeBar': True
        }
    )

    with st.expander("📝 查看各州与城市详细气温报表"):
        st.write("### 🇺🇸 各州气温")
        st.dataframe(df_states.drop(columns=["Type"]).sort_values(by="Temperature (°C)", ascending=False),
                     use_container_width=True)
        st.write("### 🏙️ 主要城市气温")
        # 如果没有打开城市开关，表格依然可以提供城市数据供查阅
        st.dataframe(df_cities.drop(columns=["Type", "City_Label"], errors='ignore').sort_values(by="Temperature (°C)",
                                                                                                 ascending=False),
                     use_container_width=True)
else:
    st.error("数据获取失败，请检查网络。")