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
      div.innerHTML = `<strong>${item.modelo}</strong><br>
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
      div.innerHTML = `<strong>Error:</strong><br>${e}`;
      contenedor.appendChild(div);
    }
  }
});

document.getElementById("descargar").addEventListener("click", () => {
  window.location.href = "/descargar_csv";
});
