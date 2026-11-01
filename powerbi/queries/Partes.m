let
    TamanoPagina = 50000,
    PrimeraPagina = fnObraPulseGet("datos", [limite = Text.From(TamanoPagina), desplazamiento = "0"]),
    Paginas = List.Generate(
        () => [Offset = 0, Page = PrimeraPagina],
        each List.Count([Page]) > 0,
        each [
            Offset = [Offset] + TamanoPagina,
            Page = fnObraPulseGet("datos", [limite = Text.From(TamanoPagina), desplazamiento = Text.From([Offset] + TamanoPagina)])
        ],
        each [Page]
    ),
    Filas = List.Combine(Paginas),
    Tabla = if List.IsEmpty(Filas) then #table({}, {}) else Table.FromRecords(Filas),
    Tipos = Table.TransformColumnTypes(Tabla, {
        {"registro_id", type text}, {"fecha", type date}, {"obra", type text},
        {"actividad", type text}, {"unidad", type text},
        {"cantidad_planificada", type number}, {"cantidad_ejecutada", type number},
        {"horas_hombre", type number}, {"precio_unitario", type number},
        {"observacion", type text}, {"semana", type date}, {"cumplida", type logical},
        {"valor_plan", type number}, {"valor_ejec", type number},
        {"valor_perdido", type number}, {"hh_perdidas", type number}, {"categoria", type text}
    }, "es-AR")
in
    Tipos
