def trans_cookies(cookies_str):
    """
    将Cookie字符串转换为字典格式

    :param cookies_str: Cookie字符串
    :return: Cookie字典
    """
    if not cookies_str:
        raise ValueError("Cookie字符串为空，请检查.env文件中的COOKIES配置")

    if '; ' in cookies_str:
        ck = {i.split('=')[0]: '='.join(i.split('=')[1:]) for i in cookies_str.split('; ')}
    else:
        ck = {i.split('=')[0]: '='.join(i.split('=')[1:]) for i in cookies_str.split(';')}

    # 检查必需的a1参数
    if 'a1' not in ck:
        raise ValueError("Cookie中缺少必需的a1参数，请确保Cookie完整且有效")

    return ck
