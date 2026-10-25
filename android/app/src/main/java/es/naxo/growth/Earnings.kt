package es.naxo.growth

import org.json.JSONObject
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit

internal data class EarningsDisplay(val label: String, val detail: String, val urgent: Boolean)

internal fun earningsDisplay(stock: JSONObject, now: Instant = Instant.now()): EarningsDisplay? {
    val event = stock.optJSONObject("earnings") ?: return null
    val raw = event.optString("date")
    val date = runCatching { LocalDate.parse(raw) }.getOrNull() ?: return null
    if (date.toString() != raw) return null
    // Recompute even for an offline dashboard: yesterday's badge must expire.
    val days = ChronoUnit.DAYS.between(now.atZone(ZoneId.of("Europe/Madrid")).toLocalDate(), date)
    if (days !in 0L..7L) return null
    val label = when (days) { 0L -> "hoy"; 1L -> "mañana"; else -> "en $days días" }
    val hour = when (event.optString("hour")) {
        "bmo" -> " · antes de la apertura"
        "amc" -> " · después del cierre"
        "dmh" -> " · durante la sesión"
        else -> ""
    }
    return EarningsDisplay("E $label", "Resultados: ${date.format(DateTimeFormatter.ofPattern("dd/MM/yyyy"))}$hour", days <= 1)
}
