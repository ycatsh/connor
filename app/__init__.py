import sys
import os

def get_path(relative_path):
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.abspath(os.path.dirname(__file__))

    return os.path.join(base_path, relative_path)

static_path = get_path('static')
font_path = get_path('fonts')
data_path = get_path('data')
tmp_path = get_path('tmp')