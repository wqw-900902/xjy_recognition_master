import os
import json
import datetime

from django.conf import settings
from django.db import models
from django.core.files.storage import FileSystemStorage


class MyFileStorage(FileSystemStorage):
    """
    自定义File Storage禁止自动重命名
    """
    # This method is actually defined in Storage
    def get_available_name(self, name, max_length):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name  # simply returns the name passed


mfs = MyFileStorage()


class School:
    """
    学校信息
    """
    # School Info
    school_name = models.CharField(max_length=50, unique=True)
    school_id = models.CharField(max_length=254, unique=True)

    # Timestamp
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '学校信息'
        verbose_name_plural = '学校信息'

    def __str__(self):
        return self.school_name


class Scanner:
    """
    扫描仪信息
    """

    # Scanner Info
    scanner_id = models.CharField(max_length=10, unique=True)
    scanner_name = models.CharField(max_length=10, null=True, blank=True)

    # Scanner Status
    last_active = models.DateTimeField(null=True, blank=True)

    # Relations
    school = models.ForeignKey(to='School', related_name='scanners', on_delete=models.PROTECT, null=True, blank=True)

    # Timestamp
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    @property
    def scanner_status(self):
        '''如果扫描仪10分钟内没有反应则为闲置状态'''

        if not self.last_active:
            return '闲置中'

        now = datetime.datetime.now().replace(tzinfo=datetime.timezone(offset=datetime.timedelta(hours=8)))
        timediff = now - self.last_active
        if timediff.total_seconds() > settings.SCANNER_ACTIVE_OFFSET:
            return '闲置中'
        return '扫描中'

    def __str__(self):
        return self.scanner_name if self.scanner_name else self.scanner_id

    class Meta:
        verbose_name = '扫描仪信息'
        verbose_name_plural = '扫描仪信息'


def upload_to(instance, filename):
    return os.path.join("img", filename.split(".")[0], filename.split("_")[-1])


class ScanResult:
    """
    扫描结果信息
    """
    STATUS_CHOICES = [
        (0, '识别中'),
        (1, '识别完毕, 上传图片中'),
        (2, '上传图片完毕, 同步至主服务器中'),
        (3, '同步至主服务器完毕'),
    ]

    # Relations
    scanner = models.ForeignKey(to='Scanner', related_name='scan_results', on_delete=models.PROTECT)

    # Scan Status
    status = models.IntegerField(default=0, choices=STATUS_CHOICES)

    # Scan Result Info
    template_id = models.CharField(max_length=254, null=True, blank=True, help_text='作业模版ID')
    exam_id = models.CharField(max_length=254, null=True, blank=True, help_text='考试模版ID 如果是考试则为考试ID，如果不是则为空')
    page_id = models.CharField(null=True,  blank=True,
                               max_length=50, help_text='页面ID 一个答题卡，有 AB CD 2张 \n 有时只识别出来A面，没有识别B面，那么pageId: A， 程序会知道，答题卡有识别，但是识别的不全, AB标识则说明2面都识别了')

    page_name = models.CharField(max_length=254, null=True, blank=True, help_text='AB面拼接文件名')
    page_file_local_path = models.CharField(max_length=254, null=True, blank=True, help_text='AB面拼接文件本地路径')

    reverted = models.BooleanField(default=False, help_text='图片是否颠倒了')

    tmp_file = models.FileField(help_text='临时文件存储路径', upload_to=upload_to, storage=mfs, null=True, blank=True)
    tmp_file_name = models.CharField(max_length=254, null=True, blank=True, help_text='临时文件名')

    file_A_name = models.CharField(max_length=254, null=True, blank=True, help_text='A面文件名')
    file_A_local_path = models.CharField(max_length=254, null=True, blank=True, help_text='A面文件本地路径')
    file_A_oss_path = models.CharField(max_length=254, null=True, blank=True, help_text='A面文件OSS路径')
    file_B_name = models.CharField(max_length=254, null=True, blank=True, help_text='B面文件名')
    file_B_local_path = models.CharField(max_length=254, null=True, blank=True, help_text='B面文件本地路径')
    file_B_oss_path = models.CharField(max_length=254, null=True, blank=True, help_text='B面文件OSS路径')
    file_C_name = models.CharField(max_length=254, null=True, blank=True, help_text='C面文件名')
    file_C_local_path = models.CharField(max_length=254, null=True, blank=True, help_text='C面文件本地路径')
    file_C_oss_path = models.CharField(max_length=254, null=True, blank=True, help_text='C面文件OSS路径')
    file_D_name = models.CharField(max_length=254, null=True, blank=True, help_text='D面文件名')
    file_D_local_path = models.CharField(max_length=254, null=True, blank=True, help_text='D面文件本地路径')
    file_D_oss_path = models.CharField(max_length=254, null=True, blank=True, help_text='D面文件OSS路径')

    student_code_write = models.CharField(max_length=254, null=True, blank=True, help_text='识别出的手写学生学号')
    student_code_write_file = models.CharField(max_length=254, null=True, blank=True, help_text='手写学生学号原始文件')
    student_code_write_confidence = models.CharField(max_length=254, null=True, blank=True, help_text='手写学生学号置信度')
    student_code = models.CharField(max_length=254, null=True, blank=True, help_text='识别出的学生学号')
    student_code_file = models.CharField(max_length=254, null=True, blank=True, help_text='学生学号原始文件')

    # JSON Result
    scanner_json = models.TextField(null=True, blank=True, help_text='从扫描仪返回的JSON')
    result_json = models.TextField(null=True, blank=True, help_text='返回給主服务器的JSON')

    # Timestamp
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.scanner.school.school_name + ' ' + self.scanner.scanner_id + ' ' + self.created.isoformat()

    class Meta:
        verbose_name = '扫描结果'
        verbose_name_plural = '扫描结果信息'


class ScanTemplate:
    """缓存用于算法识别的模版"""

    # Template Info
    template_id = models.CharField(max_length=50, unique=True)
    template_json = models.TextField(null=True, blank=True)
    template_pages = models.IntegerField(default=2)

    # Timestamp
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.template_id

    @classmethod
    def create(cls, **kwargs):
        # 根据json获取页面数量
        scan_template = cls(**kwargs)
        if kwargs['template_json']:
            t_json = json.loads(kwargs['template_json'])
            page_num = len(t_json['pages'])
            scan_template.template_pages = page_num
        return scan_template

    class Meta:
        verbose_name = '识别模版信息'
        verbose_name_plural = '识别模版信息'


class ScannerApp:
    """
    扫描仪APP
    """

    # Token Detail
    version_num = models.CharField(max_length=10, null=True, blank=True)
    download_address = models.TextField(null=True, blank=True)

    # Timestamp
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.version_num

    class Meta:
        verbose_name_plural = '扫描仪APP信息'
