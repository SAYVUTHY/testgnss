from flask import Flask, request, jsonify, render_template
import os
import sqlite3
import json
from datetime import datetime
import pandas as pd
from pyproj import Transformer
import random


app = Flask(__name__, static_folder="build", template_folder="build", static_url_path='/')
app.config['UPLOAD_FOLDER'] = 'build/files'
app.config['temp'] = 'build/files/temp'
app.config['gnss'] = 'build/files/gnss'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['temp'], exist_ok=True)
os.makedirs(app.config['gnss'], exist_ok=True)



if 'gnsslist.json' not in os.listdir(app.config['UPLOAD_FOLDER']):
    json.dump({}, open(os.path.join(app.config['UPLOAD_FOLDER'], 'gnsslist.json'), 'w'))
if 'mergegnss.json' not in os.listdir(app.config['UPLOAD_FOLDER']):
    json.dump({}, open(os.path.join(app.config['UPLOAD_FOLDER'], 'mergegnss.json'), 'w'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():

    # Check if a file is included in the request
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']

    # Check if a file was selected
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Validate file extension
    if '.db' in file.filename:
        # Securely save the file
        filename = file.filename
        filepath = os.path.join(app.config['gnss'], filename)
        file.save(filepath)
        conn = sqlite3.connect(filepath)
        df = pd.read_sql_query('SELECT dataSetName, code, localNehn, localNehe, localNehh FROM surveypointbody', conn)
        conn.close()
        df = df.rename(columns={'localNehe': 'x', 'localNehn': 'y', 'localNehh': 'z'})
        transformer = Transformer.from_crs("EPSG:32648", "EPSG:4326", always_xy=True)
        df['longitude'], df['latitude'] = zip(*df.apply(lambda row: transformer.transform(row['x'], row['y']), axis=1))
        df.to_pickle(filepath.replace('.db','.gnss'))
        os.remove(filepath)
        filename = filename.replace('.db','')
        gnsslist = json.load(open(os.path.join(app.config['UPLOAD_FOLDER'], 'gnsslist.json'), 'r'))
        if filename not in gnsslist.keys():
            gnsslist[filename] = {
                'Date': datetime.now().strftime('%d-%m-%Y %H:%M:%S'),
                'Active': 0
            }
        else:
            gnsslist[filename] = {
                'Date': datetime.now().strftime('%d-%m-%Y %H:%M:%S'),
                'Active': gnsslist[filename]['Active']
            }
        
        json.dump(gnsslist, open(os.path.join(app.config['UPLOAD_FOLDER'], 'gnsslist.json'), 'w'))
        return jsonify({'message': f'File {filename} uploaded successfully'}), 200
    else:
        return jsonify({'error': 'File type not allowed'}), 400
    

@app.route('/GNSS/listdbfile', methods = ['GET', 'POST'])
def GNSSlistdbfile():
    if request.method == 'POST':
        filename = request.form['filename']
        filepath = os.path.join(app.config['gnss'], filename+'.gnss')
        df = pd.read_pickle(filepath)
        
        random.seed(1)
        code = {}        
        for i in df['code'].drop_duplicates().values:
            if i != "" or i == "None" :
                code[str(i)] = {"colord": f"{random.randint(0, 16777215):06x}","data": df[df['code'] == i].to_dict(orient='records')}
        
        return jsonify({'success': 'login', 'data': df.to_dict(orient='records'), 'bound': [[df['latitude'].min(axis=0), df['longitude'].min(axis=0)], [df['latitude'].max(axis=0), df['longitude'].max(axis=0)]],
                        'listcode':code})

@app.route('/GNSS/removedb', methods = ['POST'])
def GNSSRemove():
    if request.method == 'POST':
        if request.form['jsonlist'] == 'mergegnss.json':
            filename = request.form['filename'] + '_merge'
        if request.form['jsonlist'] == 'gnsslist.json':
            filename = request.form['filename'] 
        
        gnsslist = json.load(open(os.path.join(app.config['UPLOAD_FOLDER'], request.form['jsonlist']), 'r'))

        gg = {}
        for i in gnsslist.keys():
            if i != filename:
                gg[i] = gnsslist[i]

        json.dump(gg, open(os.path.join(app.config['UPLOAD_FOLDER'], request.form['jsonlist']), 'w'))
        os.remove(os.path.join(app.config['gnss'], filename+'.gnss'))
        return jsonify({'success': gg})

########################## AutoMerge ###################
@app.route('/GNSS/setmerge', methods = ['POST'])
def setmerge():
    if request.method == 'POST':
        filename = request.form['filename']
        if filename != '':
            listmerge = [i for i in request.form['list'].split(',') if i != ""]
            gnsslist = json.load(open(os.path.join(app.config['UPLOAD_FOLDER'], 'mergegnss.json'), 'r'))
            # gg = {}
            # if filename not in gnsslist.keys():
            #     gg[filename] = {"listfile":listmerge, "Date": datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
            # else:
            gnsslist[filename] = {"listfile":listmerge, "Date": datetime.now().strftime('%d-%m-%Y %H:%M:%S')}

            json.dump(gnsslist, open(os.path.join(app.config['UPLOAD_FOLDER'], 'mergegnss.json'), 'w'))
            
            df = pd.concat([pd.read_pickle(os.path.join(app.config['gnss'], i+'.gnss')) for i in listmerge], axis=0)
            df.to_pickle(os.path.join(app.config['gnss'], f"{filename}_merge.gnss"))

            return jsonify({'success': 'writing complete', 'list': gnsslist})

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')