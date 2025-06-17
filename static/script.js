document.getElementById("archivo").addEventListener("change", function () {
  document.getElementById("nombreArchivo").textContent = this.files[0]?.name || "Ninguno";
});

document.getElementById("procesar").addEventListener("click", async function () {
  const archivo = document.getElementById("archivo").files[0];
  const euroInput = document.getElementById("valorEuro").value;

  if (!archivo || !euroInput) {
    alert("Debes seleccionar un archivo y proporcionar el valor del dólar en euros.");
    return;
  }

  const formData = new FormData();
  formData.append("archivo", archivo);
  formData.append("dolar_euro", euroInput);

  const response = await fetch("/procesar", { method: "POST", body: formData });
  const data = await response.json();

  const contenedor = document.getElementById("resultado");
  contenedor.innerHTML = "";

  if (data.ok) {
    for (const item of data.ok) {
      const div = document.createElement("div");
      div.className = "card success";
      div.innerHTML = `
        <strong>${item.modelo}</strong><br>
        Versión: ${item.version}<br>
        Precio: ${item.precio}<br>
        Precio (€): ${item.precio_euro}<br>
        PVP (USD): ${item.pvp_usd}<br>
        PVP (€): ${item.pvp_euro}`;
      contenedor.appendChild(div);
    }
  }

  if (data.errores) {
    for (const e of data.errores) {
      const div = document.createElement("div");
      div.className = "card error";
      const id = Math.random().toString(36).substr(2, 9);

      div.innerHTML = `
        <strong>Error:</strong><br>${e}<br><br>

        <label for="modelo-${id}">Modelo:</label>
        <input type="text" id="modelo-${id}" />

        <label for="version-${id}">Versión:</label>
        <input type="text" id="version-${id}" />

        <label for="precio-${id}">Precio USD:</label>
        <input type="number" id="precio-${id}" step="0.01" />

        <div class="botones-error">
          <button onclick="corregir('${id}')">Guardar</button>
          <button onclick="this.parentElement.parentElement.remove()">Eliminar</button>
        </div>
      `;

      contenedor.appendChild(div);
    }
  }
});

async function corregir(id) {
  const modelo = document.getElementById(`modelo-${id}`).value.trim();
  const version = document.getElementById(`version-${id}`).value.trim();
  const precio = document.getElementById(`precio-${id}`).value.trim();
  const factor = document.getElementById("valorEuro").value.trim();

  if (!modelo || !version || !precio || !factor) {
    alert("Debes completar todos los campos.");
    return;
  }

  const response = await fetch("/corregir", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      modelo,
      version,
      precio_usd: precio,
      factor
    })
  });

  const data = await response.json();

  if (!response.ok) {
    alert("Error al corregir: " + (data.error || "Error desconocido"));
    return;
  }

  const div = document.createElement("div");
  div.className = "card success";
  div.innerHTML = `
    <strong>${data.modelo}</strong><br>
    Versión: ${data.version}<br>
    Precio: ${data.precio}<br>
    Precio (€): ${data.precio_euro}<br>
    PVP (USD): ${data.pvp_usd}<br>
    PVP (€): ${data.pvp_euro}`;

  const card = document.getElementById(`modelo-${id}`).closest(".card");
  card.replaceWith(div);
}


document.getElementById("descargar").addEventListener("click", () => {
  window.location.href = "/descargar_csv";
});
