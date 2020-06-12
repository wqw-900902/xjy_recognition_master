from rest_framework import serializers

from .models import School, Scanner, ScanResult, ScannerApp, ScanTemplate


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = '__all__'


class ScannerSerializer(serializers.ModelSerializer):
    school = SchoolSerializer()
    class Meta:
        model = Scanner
        fields = '__all__'


class ScanResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanResult
        fields = '__all__'


class ScannerAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScannerApp
        fields = '__all__'


class ScanTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanTemplate
        fields = '__all__'
