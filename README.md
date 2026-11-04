# Sala de juegos

Juegos para jugar con los amigos, cada uno en su móvil. En `/` está la portada con un
juego por ficha; al pinchar en uno se abre el suyo:

| Juego | Dirección |
| --- | --- |
| ¡Paren la nave! | `/nave` (y las salas en `/s/CODIGO`) |

**Añadir un juego:** su página en `public/<juego>/index.html`, una ficha más en
`public/index.html` y, si tiene API, sus rutas en `app/` con su prefijo en
`vercel.json`. Lo de abajo es de ¡Paren la nave!

# ¡Paren la nave!

El juego de mesa de acercarse a la respuesta sin pasarse, para jugar con los amigos,
cada uno en su móvil. Uno crea la partida, pasa el enlace al grupo y a jugar: sin
cuentas, sin instalar nada.

## Cómo se juega

1. Sale una pregunta cuya respuesta es un número («¿Cuántos metros mide el Teide?»).
2. Quien abre dice una cifra y se sienta de capitán.
3. Por turnos, cada uno **sube** la cifra (y pasa a ser el capitán), **se queda** a
   bordo o grita **¡Paren la nave!** y se baja. Tras cada subida, los demás que siguen
   a bordo vuelven a decidir.
4. Cuando nadie sube, se revela la respuesta.
   - **La cifra no se pasa: la nave llega.** El capitán gana 2 puntos (4 si se queda muy
     cerca: a 5 años o a un 10 %) y cada uno de los que siguen a bordo, 1.
   - **Se pasa: la nave se estrella.** Los que se bajaron a tiempo ganan 2.
5. Tras 4 a 12 rondas (8 por defecto), gana quien más puntos tiene.

**Categorías y dificultad.** Antes de despegar (y al acabar, para la siguiente) se
eligen una o varias categorías (Historia, Geografía, Ciencia y espacio, Deportes,
Cine, series y juegos, Día a día, Infantil y Picantes 🌶️) y una o varias dificultades (Fácil,
Media, Difícil). Hay más de 500 preguntas, muchas de ellas raras y curiosas, y no se repite ninguna en la partida hasta
que se acaban las de esa categoría. La infantil (para jugar con niños) y las picantes solo salen si se eligen; con
las picantes,
también hay preguntas picantes para el alien.

**Rondas del alien.** Una ronda de cada dos (con tres o más), a uno le toca ser el
alien 👽 y se le pone la pantalla en verde. La pregunta es sobre él, de algo que no
sabe nadie más, ni su pareja, y que puede mirar en el móvil en ese momento: cuántas
fotos tiene, cuánta batería le queda, cuántos chats sin leer… La contesta en secreto
y entonces empieza la ronda para los demás; él no juega. Si la aciertan (la nave
llega y el capitán se queda muy cerca), el alien pierde 3 puntos, sin bajar de cero;
si no, gana 3. Va rotando, y si no escribe en un minuto, va una pregunta normal.

**Sin móvil también se juega.** En la sala de espera, «¿Alguien sin móvil? Juega en
este»: se le añade al móvil de otro y, cuando le toca, sale «Pásale el móvil». También
le toca ser alien, con preguntas que se contestan sin móvil: cuántas llaves lleva en el
llavero, cuántas monedas lleva encima…

Quien crea la partida manda: elige las categorías, despega y puede echar a alguien
(dos toques). Si se va, manda el siguiente.

Para irse, «Salir» arriba (dos toques). Quien vuelve con el mismo nombre recupera
sus puntos. La clasificación es de cada partida.

Quien no contesta en 45 segundos se queda a bordo; quien cierra la app no deja la
nave parada, y si no vuelve, la ronda siguiente empieza sin él.

## En local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload     # http://localhost:8000
pytest
ruff check . && ruff format .
```

## Desplegar en Vercel

La página la sirve el CDN de Vercel (`public/`) y la API, una función de Python
(`api/index.py`). Como cada petición puede caer en una función distinta, las partidas
se guardan en Redis (Upstash, plan gratis). Todo se hace desde el panel de Vercel,
también desde el móvil:

1. **Add New → Project** e importar `Proyecto_juego` de GitHub. Si no sale, «Adjust
   GitHub App Permissions» y darle acceso a ese repositorio. Sin tocar nada: **Deploy**.
2. En el proyecto, **Storage → Create Database → Upstash for Redis** (plan gratis,
   región **Frankfurt**, `eu-central-1`, la misma que las funciones: `regions` en
   `vercel.json`), y conectarla al proyecto en todos los entornos.
3. **Deployments → el último → ⋯ → Redeploy**, para que coja la base de datos.

Sin el paso 2 la app avisa: «Falta conectar la base de datos de las partidas». Cada
push a `main` se despliega solo.

**Lo que gasta:** cada móvil pregunta cada 2 segundos (una lectura) y solo se escribe
cuando cambia algo (las jugadas y, cada 8 segundos, que uno sigue ahí). Una partida
de prueba de tres jugadores, a toda prisa, gastó unas 190 órdenes en un minuto. Con
diez jugadores salen unas 25.000 por hora de juego: hay que mirar que quepan en lo
que dé el plan gratis de Upstash en cada momento.

## En un servidor propio

Sin las variables de Upstash, las partidas viven en la memoria del proceso: **un solo
proceso** (no subir los workers de uvicorn) y, si se reinicia, las partidas abiertas
se pierden. Con Docker, en un servidor con Nginx delante:

```bash
docker compose up -d --build      # escucha en 127.0.0.1:8002
```

```nginx
server {
    server_name nave.tudominio.es;
    location / {
        proxy_pass http://127.0.0.1:8002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Y el certificado con `certbot --nginx -d nave.tudominio.es`. Hace falta HTTPS para
que el botón de «Pasar el enlace» abra el menú de compartir del móvil.
