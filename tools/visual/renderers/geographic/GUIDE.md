# 地理取点图：Leaflet + 已发布的 GeoJSON

用于回答“点在哪里、是否落在目标边界内、点选后怎样查看其数据”。这是 Visual Kit 的 `custom-code` 路线；不属于既有19类咨询SVG绘制器。

## 选择与边界

- 本地或可传阅的图文 HTML：优先固定版本 **Leaflet 1.9.4 + 内嵌行政边界和取点**，无需在线瓦片、地图密钥或后端。可缩放、平移和点选。
- 只需静态说明：用相同公开几何生成内嵌 SVG，并保留坐标来源。不要手绘真实国界、州界、地形或业务覆盖范围。
- 地形、街道或卫星底图确有业务意义时再接相应服务；瓦片来源、署名、联网依赖和使用条件由调用者另行明确。地图引擎可离线不等于互联网瓦片可离线。
- 地图只呈现已给的地理事实。点位不能冒充气象站、门店、农场或代表性样本；州界归属、面积权重等计算由原任务验证。

## 输入与实际入口

先内嵌 Leaflet 的 CSS/JS，再内嵌本目录 [leaflet-points.css](leaflet-points.css)、[leaflet-points.js](leaflet-points.js)。外层容器必须有明确高度，如 `height:440px`。

```javascript
const view = VisualKitGeo.mount(document.getElementById('map'), {
  geometry: publishedGeoJSON,     // FeatureCollection；必须有来源
  featureKey: 'code',             // properties 内用作地域标识的字段
  focusId: 'TARGET_REGION',       // 必须匹配一个已提供的面要素
  points: [                      // 必须提供真实来源坐标；以下仅字段示意
    {id:'P01', label:'01', latitude:21, longitude:110,
     outside:false, description:'P01 的业务名称与所属区域'}
  ],
  grid: optionalLineGeoJSON,      // 可省略；只连真实点，不推断区域覆盖
  labels: [],                    // {text, latitude, longitude}；位置由调用者核对
  selectedId:'P01',
  initialView:'points',           // points 或 region
  attribution:'边界提供方与数据年份'
}, pointId => updateDetails(pointId));
view.fit('region');
view.fit('points');
view.select('P01');               // 只改选择，不触发回调
view.destroy();
```

`GeoJSON` 为 `[经度,纬度]`，Leaflet 的 LatLng 为 `[纬度,经度]`，不混写。经纬度与边界的坐标系必须先统一。此组件不支持极区、跨日界线或海量散点；密集视图会缩小点标记，正文保留可键盘选择的点位菜单及完整明细，放大后恢复编号。

`onSelect` 回调连接原生表格、逐日图、累计值等；不要让地图自己定义业务公式。文本字段用 `textContent`，不把外部数据直接插入 popup HTML。`attribution` 只接受纯文本，组件会转义 HTML；需要来源链接时，由调用方在图外单独创建并校验链接协议，不在署名字段中传入 HTML。

## 离线打包与许可证

上游文档：[Leaflet 下载](https://leafletjs.com/download.html)、[GeoJSON 示例](https://leafletjs.com/examples/geojson/)。2026-09-18核验的稳定版为1.9.4；升级时重新核对。

从官方列出的固定版本地址下载到调用方选择的缓存目录，并保留第三方许可：

- `https://unpkg.com/leaflet@1.9.4/dist/leaflet.js`，官方SRI：`sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=`
- `https://unpkg.com/leaflet@1.9.4/dist/leaflet.css`，官方SRI：`sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=`
- `https://unpkg.com/leaflet@1.9.4/LICENSE`

校验哈希后内嵌JS/CSS与许可证，CSS引用的PNG改成data URI，保留Leaflet及边界来源署名，移除开发用sourceMappingURL。上游JS约148KB（未压缩传输），正文、几何与脚本合计遵守Visual Kit的2MB上限。来源超链接可保留；不得有外部资源加载或运行时取数。

## 验证

真实浏览器检查：点位编号与坐标一致；点选同步更新明细；“区域全貌/放大取点”有效；窄屏不横向溢出；边界没有经纬度颠倒；无网络依赖和控制台错误。单文件应能直接从磁盘打开。库代码通过检查不代表地理代表性或业务口径成立。
