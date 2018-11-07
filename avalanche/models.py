from django.contrib.gis.db import models
from geodb.models import AfgShedaLvl4

class AfgAvsa(models.Model):
    ogc_fid = models.IntegerField(primary_key=True)
    wkb_geometry = models.MultiPolygonField(blank=True, null=True)
    avalanche_cat = models.CharField(max_length=255, blank=True)
    avalanche_id = models.IntegerField(blank=True, null=True)
    avalanche_zone = models.CharField(max_length=255, blank=True)
    avalanche_area = models.IntegerField(blank=True, null=True)
    avalanche_lenght_m = models.IntegerField(blank=True, null=True)
    dist_code = models.IntegerField(blank=True, null=True)
    dist_na_en = models.CharField(max_length=255, blank=True)
    prov_na_en = models.CharField(max_length=255, blank=True)
    prov_code = models.IntegerField(blank=True, null=True)
    basin_id = models.FloatField(blank=True, null=True)
    vuid = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=255, blank=True)
    sum_area_sqm = models.IntegerField(blank=True, null=True)
    avalanche_pop = models.IntegerField(blank=True, null=True)
    area_buildings = models.IntegerField(blank=True, null=True)
    shape_length = models.FloatField(blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    basinmember = models.ForeignKey(AfgShedaLvl4, related_name='basinmembersava')
    objects = models.GeoManager()
    class Meta:
        managed = True
        db_table = 'afg_avsa'

class AfgSnowaAverageExtent(models.Model):
    ogc_fid = models.IntegerField(primary_key=True)
    wkb_geometry = models.MultiPolygonField(blank=True, null=True)
    aver_cov = models.CharField(max_length=50, blank=True)
    cov_10_oct = models.CharField(max_length=50, blank=True)
    cov_11_nov = models.CharField(max_length=50, blank=True)
    cov_05_may = models.CharField(max_length=50, blank=True)
    cov_03_mar = models.CharField(max_length=50, blank=True)
    cov_04_apr = models.CharField(max_length=50, blank=True)
    cov_08_aug = models.CharField(max_length=50, blank=True)
    cov_12_dec = models.CharField(max_length=50, blank=True)
    cov_02_feb = models.CharField(max_length=50, blank=True)
    cov_01_jan = models.CharField(max_length=50, blank=True)
    cov_07_jul = models.CharField(max_length=50, blank=True)
    cov_06_jun = models.CharField(max_length=50, blank=True)
    cov_09_sep = models.CharField(max_length=50, blank=True)
    source = models.CharField(max_length=250, blank=True)
    author = models.CharField(max_length=250, blank=True)
    dist_code = models.IntegerField(blank=True, null=True)
    shape_length = models.FloatField(blank=True, null=True)
    shape_area = models.FloatField(blank=True, null=True)
    objects = models.GeoManager()
    class Meta:
        managed = True
        db_table = 'afg_snowa_average_extent'
