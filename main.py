import geopandas as gpd
import pandas as pd
import numpy as np
import json
import h3
import folium
import osmnx as ox
from shapely import wkt
from folium.plugins import HeatMap
from shapely.geometry import Polygon

def visualize_hexagons(hexagons, color="red", folium_map=None):

    polylines = []
    lat = []
    lng = []
    for hex in hexagons:
        polygons = h3.h3_set_to_multi_polygon([hex], geo_json=False)
        outlines = [loop for polygon in polygons for loop in polygon]
        polyline = [outline + [outline[0]] for outline in outlines][0]
        lat.extend(map(lambda v:v[0],polyline))
        lng.extend(map(lambda v:v[1],polyline))
        polylines.append(polyline)

    if folium_map is None:
        m = folium.Map(location=[sum(lat)/len(lat), sum(lng)/len(lng)], zoom_start=20, tiles='cartodbpositron')
    else:
        m = folium_map

    for polyline in polylines:
        my_PolyLine=folium.PolyLine(locations=polyline,weight=8,color=color)
        m.add_child(my_PolyLine)
    return m

'''h3_address = h3.geo_to_h3(55.35, 86.11,  9) # 9 - индекс, определяющий размер гексагона
visualize_hexagons([h3_address])'''

def visualize_polygons(geometry, folium_map=None):

    lats, lons = get_lat_lon(geometry)

    if folium_map is None:
        m = folium.Map(location=[sum(lats)/len(lats), sum(lons)/len(lons)], zoom_start=13, tiles='cartodbpositron')
    else:
        m = folium_map

    overlay = gpd.GeoSeries(geometry).to_json()
    folium.GeoJson(overlay, name = 'boundary').add_to(m)

    return m

# выводим центроиды полигонов
def get_lat_lon(geometry):

    lon = geometry.apply(lambda x: x.x if x.type == 'Point' else x.centroid.x)
    lat = geometry.apply(lambda x: x.y if x.type == 'Point' else x.centroid.y)
    return lat, lon

# выгрузим границы Кемерова из OSM
cities = ['Новокузнецкий городской округ']
polygon_krd = ox.features_from_place(cities, {'boundary':'administrative'}).reset_index()
polygon_krd = polygon_krd[(polygon_krd['name'] == 'Новокузнецкий городской округ')]
# посмотрим что получилось
visualize_polygons(polygon_krd['geometry'])

def create_hexagons(geoJson):

    polyline = geoJson['coordinates'][0]

    polyline.append(polyline[0])
    lat = [p[0] for p in polyline]
    lng = [p[1] for p in polyline]
    m = folium.Map(location=[sum(lat)/len(lat), sum(lng)/len(lng)], zoom_start=13, tiles='cartodbpositron')
    my_PolyLine=folium.PolyLine(locations=polyline,weight=8,color="green")
    m.add_child(my_PolyLine)

    hexagons = list(h3.polyfill(geoJson, 8))
    polylines = []
    lat = []
    lng = []
    for hex in hexagons:
        polygons = h3.h3_set_to_multi_polygon([hex], geo_json=False)
        # flatten polygons into loops.
        outlines = [loop for polygon in polygons for loop in polygon]
        polyline = [outline + [outline[0]] for outline in outlines][0]
        lat.extend(map(lambda v:v[0],polyline))
        lng.extend(map(lambda v:v[1],polyline))
        polylines.append(polyline)
    for polyline in polylines:
        my_PolyLine=folium.PolyLine(locations=polyline,weight=3,color='red')
        m.add_child(my_PolyLine)

    polylines_x = []
    for j in range(len(polylines)):
        a = np.column_stack((np.array(polylines[j])[:,1],np.array(polylines[j])[:,0])).tolist()
        polylines_x.append([(a[i][0], a[i][1]) for i in range(len(a))])

    polygons_hex = pd.Series(polylines_x).apply(lambda x: Polygon(x))

    return m, polygons_hex, polylines
# polygon_hex , polylines - геометрии гексагонов в разных форматах

# сгенерим гексагоны внутри полигона Кемерова
geoJson = json.loads(gpd.GeoSeries(polygon_krd['geometry']).to_json())
geoJson = geoJson['features'][0]['geometry']
geoJson = {'type':'Polygon','coordinates': [np.column_stack((np.array(geoJson['coordinates'][0])[:, 1],
                                                      np.array(geoJson['coordinates'][0])[:, 0])).tolist()]}

m, polygons, polylines = create_hexagons(geoJson)



def osm_query(tag, city):
    gdf = ox.features_from_place(city, tag).reset_index()
    gdf['city'] = np.full(len(gdf), city.split(',')[0])
    gdf['object'] = np.full(len(gdf), list(tag.keys())[0])
    gdf['type'] = np.full(len(gdf), tag[list(tag.keys())[0]])
    gdf = gdf[['city', 'object', 'type', 'geometry']]
    print(gdf.shape)
    return gdf

 # Выгрузим интересующие нас категории объектов
tags = [
        {'highway' : 'bus_stop'},
        {'office' : 'company'},
        {'tourism' : 'hotel'},
        {'tourism' : 'attraction'},
        {'tourism' : 'museum'},
        {'tourism' : 'artwork'},
        {'tourism' : 'theme_park'},
        {'tourism' : 'viewpoint'}
       ]
cities = ['Новокузнецкий городской округ']


gdfs = []
for city in cities:
    for tag in tags:
        gdfs.append(osm_query(tag, city))

# посмотрим что получилось
data_poi = pd.concat(gdfs)
data_poi.groupby(['city','object','type'], as_index = False).agg({'geometry':'count'})

# добавим координаты/центроиды
lat, lon = get_lat_lon(data_poi['geometry'])
data_poi['lat'] = lat
data_poi['lon'] = lon


# sjoin - spatial join - пересекаем гексагоны с объектами (определяем какие объекты находятся в разрезе каждого гексагона)

gdf_1 = gpd.GeoDataFrame(data_poi, geometry=gpd.points_from_xy(data_poi.lon, data_poi.lat))

gdf_2 = pd.DataFrame(polygons, columns = ['geometry'])
gdf_2['polylines'] = polylines
gdf_2['geometry'] = gdf_2['geometry'].astype(str)
geometry_uniq = pd.DataFrame(gdf_2['geometry'].drop_duplicates())
geometry_uniq['id'] = np.arange(len(geometry_uniq)).astype(str)
gdf_2 = gdf_2.merge(geometry_uniq, on = 'geometry')
gdf_2['geometry'] = gdf_2['geometry'].apply(wkt.loads)
gdf_2 = gpd.GeoDataFrame(gdf_2, geometry='geometry')

itog_table = gpd.sjoin(gdf_2, gdf_1, how='left', op='intersects')
itog_table = itog_table.dropna()
itog_table.head()


def create_choropleth(data, json, columns, legend_name, feature, bins):

    lat, lon = get_lat_lon(data['geometry'])

    m = folium.Map(location=[sum(lat)/len(lat), sum(lon)/len(lon)], zoom_start=13, tiles='cartodbpositron')

    folium.Choropleth(
        geo_data=json,
        name="choropleth",
        data=data,
        columns=columns,
        key_on="feature.id",
        fill_color="YlGn",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=legend_name,
        nan_fill_color = 'black',
        bins = bins

    ).add_to(m)

    folium.LayerControl().add_to(m)

    return m


# подготовим данные
itog_table['geometry'] = itog_table['geometry'].astype(str) #для groupby
itog_table['id'] = itog_table['id'].astype(str) #для Choropleth
agg_all = itog_table.groupby(['geometry','type','id'], as_index = False).agg({'lat':'count'}).rename(columns = {'lat':'counts'})
agg_all['geometry'] = agg_all['geometry'].apply(wkt.loads) #возвращаем формат геометрий

agg_all_hotel = agg_all.query("type == 'hotel'")[["geometry","counts",'id']]
agg_all_hotel['id'] = agg_all_hotel['id'].astype(str)
data_geo_1 = gpd.GeoSeries(agg_all_hotel.set_index('id')["geometry"]).to_json()

create_choropleth(agg_all_hotel, data_geo_1, ["id","counts"], 'Hotel counts', 'counts', 4)
m.save('my_map.html')
#data_poi # координаты объектов
#itog_table # объекты и их шестиугольники
#bus_stops = itog_table.loc[itog_table['type'] == 'bus_stop']
#bus_stops


DICT = {}
for element in range(len(itog_table['geometry'])):
    gl = itog_table['geometry'].values.tolist()
    tl = itog_table['type'].values.tolist()
    if not (gl[element] in DICT):
        DICT[gl[element]] = {}
    if not(tl[element] in DICT[gl[element]]):
        DICT[gl[element]][tl[element]] = 0
    DICT[gl[element]][tl[element]] += 1
df = pd.DataFrame(DICT)
df = df.T
'''a = df.mean(axis=0, skipna=True)
df = df.fillna({'bus_stop': a['bus_stop']})'''
df = df.fillna(0)
df['landmark'] = df['artwork'] + df['theme_park'] + df['museum'] + df['attraction'] + df['viewpoint']
df = df.drop('artwork', axis=1)
df = df.drop('theme_park', axis=1)
df = df.drop('museum', axis=1)
df = df.drop('attraction', axis=1)
df = df.drop('viewpoint', axis=1)
df.to_csv('nvkz.csv')

'''
old = 0
new = 0
ind = 0
for i in range(162):
    new = (df['landmark'].loc[df.index[i]]+df['bus_stop'].loc[df.index[i]]+df['company'].loc[df.index[i]])/df['hotel'].loc[df.index[i]]
    if new > old:
        old = new
        ind = i
print(df.iloc[[ind]])'''