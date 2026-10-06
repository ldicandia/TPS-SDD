# Spec — <cambio> en `<proyecto>`

**Base:** `<proyecto>` @ `<hash de git rev-parse HEAD>` · **Fecha:** <AAAA-MM-DD>

## Propósito

<Una oración: qué puede hacer quién que hoy no puede. Sin nombrar tecnología.>

## Términos

| Término | Significa |
|---|---|
| <término> | <definición única; en toda la spec se usa esta palabra y no un sinónimo> |

## Alcance

### Dentro

| Archivo / módulo | Qué cambia |
|---|---|
| `<ruta/archivo>` | <qué se agrega o modifica> |

### Fuera

| Qué queda afuera | Por qué |
|---|---|
| <módulo, flag o comportamiento concreto> | <razón; si es "para después", va al plan, no a esta spec> |

## Invariantes

### INV-1 · <algo que hoy funciona y este cambio no puede romper>

<Enunciado observable.>

- **VC-INV-1** · `<comando que lo comprueba, p. ej. la suite existente>` → <resultado esperado>

## Requerimientos

### FR-1 · <comportamiento nuevo, en una línea>

- **Dado** <estado inicial concreto, con los datos que hacen falta>
- **Cuando** <acción exacta>
- **Entonces** <resultado observable: salida, exit code, archivo>
- **VC-FR-1** · `<comando o entrada exacta>` → <salida y exit code esperados>

### NFR-1 · <atributo medible>

<Métrica, umbral y carga con números. Si no hay NFR, borrá esta sección.>

- **VC-NFR-1** · `<cómo se mide>` → <umbral>

## Decisiones

| ID | Decisión | Alternativa descartada | Fundamento en el código base |
|---|---|---|---|
| D-1 | <qué se eligió> | <qué no se eligió> | `<archivo>:<línea>` <qué hace ese código que sostiene la elección> |

## Trazabilidad

<Pegá acá la tabla que imprime check_spec.py cuando la spec pasa.>
