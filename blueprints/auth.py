import random
import time
from datetime import datetime

from flask import Blueprint, redirect, render_template, request, session, url_for, make_response, jsonify

import DB


# Crea un altro Blueprint
auth_bp = Blueprint('auth', __name__,url_prefix='/')

@auth_bp.route('/')
def index():
    return render_template('prova.html')