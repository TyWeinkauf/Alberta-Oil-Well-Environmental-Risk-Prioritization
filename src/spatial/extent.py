"""Densified WGS84 study boundary transformed to the common metre CRS."""
from pyproj import Transformer
from shapely import transform
from shapely.geometry import Polygon
from src.config import StudyArea


def study_geometry(area: StudyArea):
    west,south,east,north=area.bbox_wgs84
    points=[]
    for start,end in [((west,south),(east,south)),((east,south),(east,north)),
                      ((east,north),(west,north)),((west,north),(west,south))]:
        points.extend([(start[0]+(end[0]-start[0])*i/32,start[1]+(end[1]-start[1])*i/32) for i in range(32)])
    return transform(Polygon(points),Transformer.from_crs(4326,3400,always_xy=True).transform,interleaved=False)
