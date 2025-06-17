from flask import Flask, request, jsonify, send_file, render_template
import pandas as pd
import re
import io
import csv
import math

app = Flask(__name__)

resultados_ok = []
resultados_error = []
ultimo_modelo = None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/procesar", methods=["POST"])
def procesar():
    global resultados_ok, resultados_error, ultimo_modelo
    resultados_ok = []
    resultados_error = []
    ultimo_modelo = None

    archivo = request.files["archivo"]
    factor = float(request.form.get("dolar_euro", "1.0"))

    if not archivo:
        return jsonify({"error": "No se recibió archivo"}), 400

    try:
        nombre = archivo.filename
        if nombre.endswith(".xlsx"):
            df = pd.read_excel(archivo)
            parsear_excel_especializado(df, factor)
        elif nombre.endswith(".csv"):
            df = pd.read_csv(archivo)
            for _, fila in df.iterrows():
                parse(str(fila), factor)
        elif nombre.endswith(".txt"):
            for linea in archivo.stream:
                parse(linea.decode("utf-8"), factor)
        else:
            return jsonify({"error": "Formato no soportado"}), 400

        return jsonify({
            "ok": resultados_ok,
            "errores": resultados_error,
            "nombre_archivo": nombre
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/agregar_manual", methods=["POST"])
def agregar_manual():
    global resultados_ok
    data = request.get_json()
    modelo = data.get("modelo")
    version = data.get("version")
    precio = data.get("precio_usd")
    factor = float(data.get("factor", 1.0))

    try:
        precio = float(precio)
        registrar_resultado(modelo, version, precio, factor)
        return jsonify(resultados_ok[-1])
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/descargar_csv")
def descargar_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Modelo", "Versión", "Precio USD", "Precio EUR", "PVP USD", "PVP EUR"])
    for r in resultados_ok:
        writer.writerow([r["modelo"], r["version"], r["precio"], r["precio_euro"], r["pvp_usd"], r["pvp_euro"]])
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name="maquinas_procesadas.csv")

def detectar_numero(precio_str):
    precio_str = precio_str.strip().replace(" ", "")
    if ',' not in precio_str and '.' in precio_str and len(precio_str.split('.')[-1]) == 3:
        return float(precio_str.replace('.', ''))
    return float(precio_str.replace(',', '.'))

def extraer_versiones(raw):
    versiones = []
    sufijo = 'T'
    bloques = re.split(r'[/,;]', raw)
    for bloque in bloques:
        bloque = bloque.strip()
        if not bloque:
            continue
        match_rango = re.match(r'^(\d+)-(\d+)([TtGg])$', bloque)
        if match_rango:
            ini, fin, suf = match_rango.groups()
            for i in (int(ini), int(fin)):
                versiones.append(f"{i}{suf.upper()}")
            continue
        match_solo_numeros = re.match(r'^(\d+)-(\d+)$', bloque)
        if match_solo_numeros:
            ini, fin = match_solo_numeros.groups()
            for i in (int(ini), int(fin)):
                versiones.append(f"{i}{sufijo}")
            continue
        if re.search(r'[TtGg]$', bloque):
            versiones.append(bloque.upper())
            sufijo = bloque[-1].upper()
        else:
            versiones.append(f"{bloque}{sufijo}")
    return versiones

def parsear_excel_especializado(df, factor):
    headers = ['Coin', 'Brand', 'Model', 'Hashrate/T', 'Efficiency', 'Price/T', 'Unit Price', 'MOQ', 'Delivery Time']
    for i, row in df.iterrows():
        if all(h in row.values for h in headers):
            df.columns = row.values
            df = df.iloc[i + 1:].reset_index(drop=True)
            break

    df = df[headers]
    df['Model'] = df['Model'].ffill()

    for _, fila in df.iterrows():
        try:
            modelo = str(fila.get('Model', '')).strip()
            if not modelo or modelo.lower() == 'nan':
                continue

            versiones_raw = str(fila.get('Hashrate/T', '')).strip()
            unit_price_raw = str(fila.get('Unit Price', '')).strip()
            price_per_t_raw = str(fila.get('Price/T', '')).strip()

            if not versiones_raw or versiones_raw.lower() == 'nan':
                resultados_error.append(str(fila.to_dict()))
                continue

            versiones = extraer_versiones(versiones_raw)

            if unit_price_raw and unit_price_raw.lower() != 'nan':
                precio_fijo = detectar_numero(unit_price_raw)
                for v in versiones:
                    registrar_resultado(modelo, v, precio_fijo, factor)
            elif price_per_t_raw and price_per_t_raw.lower() != 'nan':
                price_t = detectar_numero(price_per_t_raw)
                if price_t > 100:
                    for v in versiones:
                        registrar_resultado(modelo, v, price_t, factor)
                else:
                    for v in versiones:
                        valor = float(re.sub(r'[^\d.]', '', v))
                        total = round(valor * price_t, 2)
                        registrar_resultado(modelo, v, total, factor)
            else:
                resultados_error.append(str(fila.to_dict()))
        except Exception:
            resultados_error.append(str(fila.to_dict()))

def parse(linea, factor):
    global ultimo_modelo
    matches = re.findall(r'([^\s]*[TtG](?:[/\-][^\s]*)*)', linea)
    modelo = None
    hashrates = []

    for bloque in matches:
        if not re.search(r'\d', bloque): continue
        if re.search(r'[TtG](?=[A-Za-z])', bloque): continue
        segmento = linea.split(bloque)[0].strip()
        if segmento:
            modelo = segmento
            ultimo_modelo = modelo
        elif ultimo_modelo:
            modelo = ultimo_modelo
        hashrates = extraer_versiones(bloque)
        break

    if not modelo or not hashrates:
        resultados_error.append(linea.strip())
        return

    bloque_precios_match = re.search(r'\$([^\s]+)', linea)
    if not bloque_precios_match:
        resultados_error.append(linea.strip())
        return

    bloque_precios = bloque_precios_match.group(1).split('/')
    precios_version = []
    for p in bloque_precios:
        p = p.strip().rstrip('T').replace(',', '.')
        try:
            precios_version.append(detectar_numero(p))
        except:
            pass

    if len(precios_version) == 1 and precios_version[0] > 100:
        for hr in hashrates:
            registrar_resultado(modelo, hr, precios_version[0], factor)
        return

    if all(p <= 100 for p in precios_version):
        if len(precios_version) == len(hashrates):
            precios_por_version = precios_version
        elif len(precios_version) == 1:
            precios_por_version = precios_version * len(hashrates)
        else:
            resultados_error.append(linea.strip())
            return
    else:
        resultados_error.append(linea.strip())
        return

    for idx, hr in enumerate(hashrates):
        valor = float(re.sub(r'[^\d.]', '', hr))
        if '.' in hr and len(hr.split('.')[-1]) > 2:
            valor = int(valor)
        total = round(valor * precios_por_version[idx], 2)
        registrar_resultado(modelo, hr, total, factor)

def registrar_resultado(modelo, version, precio_usd, factor):
    precio_usd_redondeado = math.ceil(precio_usd)
    precio_euro = round(precio_usd_redondeado * factor, 2)
    pvp_usd = round(precio_usd_redondeado * 1.25, 2)
    pvp_euro = round(precio_euro * 1.25, 2)
    resultados_ok.append({
        "modelo": modelo,
        "version": version,
        "precio": f"{precio_usd_redondeado}$",
        "precio_euro": f"{precio_euro}€",
        "pvp_usd": f"{pvp_usd}$",
        "pvp_euro": f"{pvp_euro}€"
    })

if __name__ == "__main__":
    app.run(debug=True)
