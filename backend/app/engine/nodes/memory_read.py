from __future__ import annotations

from app.engine.nodes.base import Turn
from app.memory import store
from app.tools import data


async def run(turn: Turn) -> None:
    st = turn.state
    turn.emit(
        "memoria",
        "node_start",
        "Leer memoria",
        {
            "claves": [
                f"sesion:{st.sesion_id}:historial",
                f"cliente:{st.cliente_id}:perfil",
                f"cliente:{st.cliente_id}:episodios",
            ]
        },
    )
    st.historial = await store.historial(st.sesion_id)
    st.perfil = await store.perfil(st.cliente_id)
    st.episodios = await store.episodios(st.cliente_id)
    c = await data.cliente(st.cliente_id)
    st.cliente_nombre = c["nombre"] if c else ""
    st.tienda = st.perfil.get("tienda") or (c["tienda"] if c else "LC")
    if c and "canal" not in st.perfil and st.canal == "app":
        st.canal = c.get("canal") or st.canal
    turn.emit(
        "memoria",
        "memory",
        f"{len(st.historial)} turnos · {len(st.perfil)} hechos · {len(st.episodios)} episodios",
        {"historial": st.historial[-6:], "perfil": st.perfil, "episodios": st.episodios[-3:], "tienda": st.tienda},
    )
    turn.emit("memoria", "node_end", "Memoria lista")
