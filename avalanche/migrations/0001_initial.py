# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.contrib.gis.db.models.fields


class Migration(migrations.Migration):

    dependencies = [
        ('geodb', '0003_auto_20181102_0514'),
    ]

    operations = [
        migrations.CreateModel(
            name='AfgAvsa',
            fields=[
                ('ogc_fid', models.IntegerField(serialize=False, primary_key=True)),
                ('wkb_geometry', django.contrib.gis.db.models.fields.MultiPolygonField(srid=4326, null=True, blank=True)),
                ('avalanche_cat', models.CharField(max_length=255, blank=True)),
                ('avalanche_id', models.IntegerField(null=True, blank=True)),
                ('avalanche_zone', models.CharField(max_length=255, blank=True)),
                ('avalanche_area', models.IntegerField(null=True, blank=True)),
                ('avalanche_lenght_m', models.IntegerField(null=True, blank=True)),
                ('dist_code', models.IntegerField(null=True, blank=True)),
                ('dist_na_en', models.CharField(max_length=255, blank=True)),
                ('prov_na_en', models.CharField(max_length=255, blank=True)),
                ('prov_code', models.IntegerField(null=True, blank=True)),
                ('basin_id', models.FloatField(null=True, blank=True)),
                ('vuid', models.CharField(max_length=255, blank=True)),
                ('source', models.CharField(max_length=255, blank=True)),
                ('sum_area_sqm', models.IntegerField(null=True, blank=True)),
                ('avalanche_pop', models.IntegerField(null=True, blank=True)),
                ('area_buildings', models.IntegerField(null=True, blank=True)),
                ('shape_length', models.FloatField(null=True, blank=True)),
                ('shape_area', models.FloatField(null=True, blank=True)),
                ('basinmember', models.ForeignKey(related_name='basinmembersava', to='geodb.AfgShedaLvl4')),
            ],
            options={
                'db_table': 'afg_avsa',
                'managed': True,
            },
        ),
        migrations.CreateModel(
            name='AfgSnowaAverageExtent',
            fields=[
                ('ogc_fid', models.IntegerField(serialize=False, primary_key=True)),
                ('wkb_geometry', django.contrib.gis.db.models.fields.MultiPolygonField(srid=4326, null=True, blank=True)),
                ('aver_cov', models.CharField(max_length=50, blank=True)),
                ('cov_10_oct', models.CharField(max_length=50, blank=True)),
                ('cov_11_nov', models.CharField(max_length=50, blank=True)),
                ('cov_05_may', models.CharField(max_length=50, blank=True)),
                ('cov_03_mar', models.CharField(max_length=50, blank=True)),
                ('cov_04_apr', models.CharField(max_length=50, blank=True)),
                ('cov_08_aug', models.CharField(max_length=50, blank=True)),
                ('cov_12_dec', models.CharField(max_length=50, blank=True)),
                ('cov_02_feb', models.CharField(max_length=50, blank=True)),
                ('cov_01_jan', models.CharField(max_length=50, blank=True)),
                ('cov_07_jul', models.CharField(max_length=50, blank=True)),
                ('cov_06_jun', models.CharField(max_length=50, blank=True)),
                ('cov_09_sep', models.CharField(max_length=50, blank=True)),
                ('source', models.CharField(max_length=250, blank=True)),
                ('author', models.CharField(max_length=250, blank=True)),
                ('dist_code', models.IntegerField(null=True, blank=True)),
                ('shape_length', models.FloatField(null=True, blank=True)),
                ('shape_area', models.FloatField(null=True, blank=True)),
            ],
            options={
                'db_table': 'afg_snowa_average_extent',
                'managed': True,
            },
        ),
    ]
