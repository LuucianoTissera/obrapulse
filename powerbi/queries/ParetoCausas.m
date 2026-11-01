let
    Source = fnObraPulseGet("pareto", [por = "categoria"]),
    Tabla = if List.IsEmpty(Source) then #table({}, {}) else Table.FromRecords(Source),
    Tipos = Table.TransformColumnTypes(Tabla, {
        {"categoria", type text}, {"desvios", Int64.Type}, {"valor_perdido", type number},
        {"hh_perdidas", type number}, {"pct", type number}, {"pct_acum", type number}
    }, "es-AR")
in
    Tipos
