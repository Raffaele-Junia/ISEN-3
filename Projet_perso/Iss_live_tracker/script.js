const EARTH_RADIUS = 6371;

const globe = Globe()
    (document.getElementById("globe"))

    .globeImageUrl(
        "https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
    )

    .bumpImageUrl(
        "https://unpkg.com/three-globe/example/img/earth-topology.png"
    )

    .backgroundImageUrl(
        "https://unpkg.com/three-globe/example/img/night-sky.png"
    )

    .showAtmosphere(true)

    .atmosphereAltitude(0.12)

    .pointColor(() => "#ff3333")

    .pointRadius(0.7)

    .pointAltitude(
        d => d.altitude / EARTH_RADIUS
    )

    .pointLabel(
        d => `
            <div style="
                background: black;
                color: white;
                padding: 8px;
                border-radius: 8px;
            ">
                🛰️ <b>International Space Station</b>
                <br>
                Altitude: ${d.altitude.toFixed(1)} km
            </div>
        `
    )

    .pathColor(() => "#ff3333")

    .pathStroke(2);


globe.controls().autoRotate = true;

globe.controls().autoRotateSpeed = 0.2;

globe.controls().enableDamping = true;


let iss = [];

let trajectory = [];


async function getISSPosition() {

    try {

        const response = await fetch(
            "https://api.wheretheiss.at/v1/satellites/25544"
        );

        if (!response.ok) {

            throw new Error(
                `Erreur HTTP ${response.status}`
            );

        }

        const data = await response.json();


        const latitude = Number(data.latitude);

        const longitude = Number(data.longitude);

        const altitude = Number(data.altitude);

        const velocity = Number(data.velocity);


        document.getElementById("latitude").textContent =
            latitude.toFixed(2) + "°";


        document.getElementById("longitude").textContent =
            longitude.toFixed(2) + "°";


        document.getElementById("altitude").textContent =
            altitude.toFixed(1) + " km";


        document.getElementById("velocity").textContent =
            (velocity / 1000).toFixed(2) + " km/s";


        document.getElementById("updated").textContent =
            new Date().toLocaleTimeString();


        document.getElementById("status").textContent =
            "🟢 Position mise à jour";


        iss = [
            {
                lat: latitude,
                lng: longitude,
                altitude: altitude
            }
        ];


        trajectory.push([
            longitude,
            latitude,
            altitude
        ]);


        if (trajectory.length > 120) {

            trajectory.shift();

        }


        globe
            .pointsData(iss)
            .pathsData([
                {
                    coords: trajectory
                }
            ]);


    } catch (error) {

        console.error(error);

        document.getElementById("status").textContent =
            "🔴 Impossible de récupérer la position";

    }

}


document
    .getElementById("centerISS")
    .addEventListener("click", () => {

        if (iss.length === 0) {

            return;

        }


        const latitude = iss[0].lat;

        const longitude = iss[0].lng;


        globe.pointOfView(
            {
                lat: latitude,

                lng: longitude,

                altitude: 2
            },

            1000
        );

    });


getISSPosition();


setInterval(
    getISSPosition,
    5000
);