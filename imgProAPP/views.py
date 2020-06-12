import datetime
import json
import requests
import cv2
from pyzbar.pyzbar import decode
from PIL import Image
import numpy as np
from django.conf import settings
from django.utils import timezone
from django.db import IntegrityError
from django.core.cache import cache
# from django.core.files import File
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response
# from rest_framework.permissions import AllowAny, IsAuthenticated
import os
from django_q.tasks import async_task, result

from .serializers import School, Scanner, ScanResult, ScannerApp, ScanTemplate, SchoolSerializer, ScannerSerializer, ScanResultSerializer, ScannerAppSerializer, ScanTemplateSerializer
# from .utils.algorithm import score_system
from .utils.preprocess_img import process
from .tasks import scorePaper
import redis


def get_next_file_name(file_name, direction):
    file_name_splited = file_name.split('_')
    file_num_len = len(file_name_splited[-1])
    file_num = int(file_name_splited[-1])
    file_name_splited[-1] = format(file_num + direction, '0'+str(file_num_len)+'d')
    file_name_new = '_'.join(file_name_splited)
    return file_name_new


@api_view(['GET'])
def check_app_view(request):
    '''
    检查扫描仪APP是否有更新
    '''
    scanner_app = ScannerApp.objects.all().first()

    if scanner_app:
        return Response(ScannerAppSerializer(scanner_app).data)
    else:
        return Response({})


@api_view(['POST'])
@parser_classes([JSONParser])
def update_school_scanner_view(request, school_id=None, scanner_id=None):
    '''
    更新扫描仪与学校的对应关系
    '''
    if not (school_id and scanner_id):
        return Response({'Error': '请求路径中无学校ID或扫描仪ID'}, status=400)

    school = School.objects.filter(school_id=school_id).first()
    scanner = Scanner.objects.filter(scanner_id=scanner_id).first()

    if not school:
        return Response({'Error': '学校不存在'}, status=400)

    if not scanner:
        scanner = Scanner.objects.create(scanner_id=scanner_id, school=school, scanner_name=school.school_name + '扫描仪')

    return Response(ScannerSerializer(scanner).data, status=200)


@api_view(['GET'])
def active_scanner_view(request):
    '''
    返回活跃的扫描仪数量
    '''
    now = timezone.now()
    past = now - datetime.timedelta(seconds=settings.SCANNER_ACTIVE_OFFSET)
    scanners = Scanner.objects.filter(last_active__gt=past)
    return Response(ScannerSerializer(scanners, many=True).data, status=200)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def file_upload_view(request, school_id=None, scanner_id=None):
    if not school_id or not scanner_id:
        cache.set("request_error_msg", settings.REQUEST_PARAMS_ERROR)
        return Response({'Error': '请求路径中无学校ID或扫描仪ID'}, status=400)
    # 更新扫描仪last active
    scanner = Scanner.objects.filter(scanner_id=scanner_id).first()
    # 如果扫描仪不存在则直接创建
    if not scanner:
        school = School.objects.filter(school_id=school_id).first()
        scanner = Scanner.objects.create(scanner_id=scanner_id, school=school, scanner_name=school.school_name + '扫描仪')
    scanner.last_active = timezone.now()
    scanner.save()
    # 这个json文件的内容是什么？客户端上传的每一张图片的json信息
    scanner_json = json.loads(request.POST['json'])
    # 创建基本scan result实例
    scan_result = ScanResult()
    scan_result.scanner = scanner
    # 将上传的json文件作为当前图片扫描信息格式进行存储对应的结果
    scan_result.scanner_json = scanner_json
    # 先将图片存入本地
    scan_result.tmp_file = request.FILES['file']
    scan_result.tmp_file_name = request.FILES['file'].name.split('.')[0]
    scan_result.save()
    # 图片正畸和切边, 同时返回页码和是否反转
    reverted, page = process(scan_result.tmp_file.path, scan_result.tmp_file_name)

    # "qr_code_scanned": false, 客户端是否对二维码进行了扫描
    qr_code_scanned = scanner_json['qr_code_scanned']
    qr_code = None

    # 取余为1 则为本张页面的第一页，就是有二维码的页面
    if page % 2 == 1:
        if qr_code_scanned:
            qr_code = None if not qr_code_scanned else scanner_json['qr_code']
        else:
            qr = decode(Image.open(scan_result.tmp_file))
            qr_code = qr[0][0].decode("utf-8") if qr else None


    # 如果有二维码
    if qr_code:
        page = 1
        # 二维码中的key作为模板的ID
        scan_result.template_id = qr_code
        # TODO: 需要求证exam id和template id的区分
        if 'exam' in scan_result.template_id:
            scan_result.exam_id = scan_result.template_id
        scan_result.file_A_name = scan_result.tmp_file_name
        scan_result.file_A_local_path = scan_result.tmp_file.path
    else:
        # 没有二维码则认为是第二页
        page = 2
        # 获取template id
        file_scan_result = get_file_scan_result(scan_result.tmp_file_name)
        scan_result.template_id = file_scan_result.template_id if file_scan_result else None
    # 保存页面是否翻转以及页面信息
    scan_result.reverted = reverted
    scan_result.page_id = page
    scan_result.save()
    # 如果是第一张图片就是第二页的话，则需要获取第一页的
    scan_template_json = get_template_json(scan_result.template_id)
    if not scan_template_json:
        print("尝试获取模板json失败")
        return Response({'Info': '尝试获取模板json失败，pageB对应的pageA不存在！！'}, status=200)
    # 合并scan result
    # TODO C面和D面
    scan_result = merge_page(page, reverted, scan_result)
    if not scan_result:
        return Response({'Info': '尝试合并scan_result时pageB存在pageA不存在'}, status=200)
    # 调用图像识别算法
    # async_task('img_process_web_server.tasks.scorePaper', scan_result, scan_template_json)
    scorePaper(scan_result, scan_template_json)
    return Response(status=200)


def get_file_scan_result(file_name):
    file_name_num = int(file_name.split('_')[-1].split('.')[0])
    if file_name_num % 2 == 0:
        # B面存在找A面
        temp_name = get_next_file_name(file_name, -1)
    else:
        # A面存在找B面
        temp_name = get_next_file_name(file_name, 1)

    file_scan_result = ScanResult.objects.filter(tmp_file_name=temp_name).first()
    return file_scan_result


# 合并page B 和 page A，删除B的一份
def merge_page(page, reverted, one_scan_result):
    another_scan_result = get_file_scan_result(one_scan_result.tmp_file_name)
    if not another_scan_result:
        return None
    scan_result = None
    if page == 1:  # A面存在找B面
        scan_result = merge(one_scan_result, another_scan_result)
    elif page == 2:  # B面存在找A面
        scan_result = merge(another_scan_result, one_scan_result)
    page_path = concate_page(scan_result.file_A_local_path, scan_result.file_B_local_path)
    scan_result.page_file_local_path = page_path
    scan_result.page_name = page_path.split(os.sep)[-1]
    delete_page_b(scan_result.file_B_name)
    return scan_result


def delete_page_b(file_b_name):
    file_scan = ScanResult.objects.filter(tmp_file_name=file_b_name).first()
    if file_scan:
        file_scan.delete()


# 合并page B 和 page A，删除B的一份
def merge(file_a_scan_result, file_b_scan_result):
    # print("扫描文件结果：", file_b_scan_result)
    file_a_scan_result.file_A_name = file_a_scan_result.tmp_file_name
    file_a_scan_result.file_A_local_path = file_a_scan_result.tmp_file.path
    file_a_scan_result.file_B_name = file_b_scan_result.tmp_file_name
    file_a_scan_result.file_B_local_path = file_b_scan_result.tmp_file.path
    file_b_scan_result.delete()
    file_a_scan_result.tmp_file_name = None
    file_a_scan_result.tmp_file = None
    file_a_scan_result.page_id = 'AB'
    file_a_scan_result.save()
    return file_a_scan_result


def concate_page(img_path1, img_path2):
    page_a = cv2.imread(img_path1)
    page_b = cv2.imread(img_path2)
    page_b = cv2.resize(page_b, (page_a.shape[1], page_a.shape[0]))
    page = np.concatenate((page_a, page_b))
    img_path = img_path1.split(".")[0] + "_" + img_path2.split(os.sep)[-1]
    cv2.imwrite(img_path, page)
    return img_path


def get_template_json(template_id):
    try:
        if not template_id:
            return None
        scan_template = ScanTemplate.objects.filter(template_id=template_id).first()
        # 如果数据库中没有缓存当前template id对应的模版，从主服务器获取
        if scan_template:
            scan_template_json = scan_template.template_json
        else:
            scan_template = ScanTemplate.objects.create(template_id=template_id)
            # 从主服务器获取模版信息并缓存本地
            print("开始获取模型json")
            resp = requests.get(settings.MAIN_SERVER_URL +
                                'resolve_server/resolve/template/' + template_id)
            while not resp.json():
                print("再次获取模型json")
                resp = requests.get(settings.MAIN_SERVER_URL +
                                    'resolve_server/resolve/template/' + template_id)
            print("获取模板json成功！！")
            scan_template_json = resp.json()['data']
            # 补上模版信息
            scan_template.template_json = scan_template_json
            scan_template.save()
        return scan_template_json
    except IntegrityError as e:
        print(e)
        pass
        # 如果两个进程同时尝试创建模版，并发生冲突，则跳过这步
    # 获取识别模版
    # scan_template = ScanTemplate.objects.filter(template_id=scan_result.template_id).first()
    # if not scan_template:  # 如果其他进程在从网络下载模版, 等待
    #     # time.sleep(5)
    #     try:
    #         scan_template = ScanTemplate.objects.get(template_id=scan_result.template_id)
    #     except ScanTemplate.DoesNotExist:
    #         if scan_result.template_id:
    #             return Response({'Error': '因并页失败导致无法获取tempalte id, 进而无法获得template json'}, status=400)
    #         else:
    #             return Response({'Error': '获取template失败'}, status=400)


