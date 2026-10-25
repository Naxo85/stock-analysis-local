package es.naxo.growth

import java.time.Instant
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class EarningsTest {
    private fun stock(date: String) = JSONObject().put("earnings", JSONObject().put("date", date))
    private val now = Instant.parse("2026-10-21T12:00:00Z")
    @Test fun windowAndColours() {
        assertEquals("E hoy", earningsDisplay(stock("2026-10-21"), now)?.label)
        assertTrue(earningsDisplay(stock("2026-10-22"), now)!!.urgent)
        assertFalse(earningsDisplay(stock("2026-10-23"), now)!!.urgent)
        assertEquals("E en 7 días", earningsDisplay(stock("2026-10-28"), now)?.label)
        assertNull(earningsDisplay(stock("2026-10-29"), now))
        assertNull(earningsDisplay(stock("2026-10-20"), now))
    }
    @Test fun offlineBadgeExpiresAtMadridMidnight() {
        val same = stock("2026-10-21")
        assertNotNull(earningsDisplay(same, Instant.parse("2026-10-21T21:59:59Z")))
        assertNull(earningsDisplay(same, Instant.parse("2026-10-21T22:00:00Z")))
    }
    @Test fun unknownAndInvalidDoNotShow() {
        for (date in listOf("?", "", "2026-02-30", "20261021")) assertNull(earningsDisplay(stock(date), now))
        assertNull(earningsDisplay(JSONObject(), now))
    }
    @Test fun onlyKnownHoursAreDisplayed() {
        val same = stock("2026-10-21")
        assertEquals("Resultados: 21/10/2026", earningsDisplay(same, now)?.detail)
        same.getJSONObject("earnings").put("hour", "amc")
        assertTrue(earningsDisplay(same, now)!!.detail.endsWith("después del cierre"))
    }
}
