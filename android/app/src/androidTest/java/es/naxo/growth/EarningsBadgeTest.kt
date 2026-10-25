package es.naxo.growth

import androidx.compose.foundation.layout.Column
import androidx.compose.material3.Surface
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import java.time.LocalDate
import java.time.ZoneId
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test

class EarningsBadgeTest {
    @get:Rule val compose = createComposeRule()
    @Test fun calendarLabelsAreVisibleAndUnknownHasNoBadge() {
        val today = LocalDate.now(ZoneId.of("Europe/Madrid"))
        fun stock(days: Long) = JSONObject().put("earnings", JSONObject().put("date", today.plusDays(days).toString()))
        compose.setContent { GrowthTheme(false) { Surface { Column {
            EarningsBadge(stock(0)); EarningsBadge(stock(1)); EarningsBadge(stock(7))
            EarningsBadge(stock(-1)); EarningsBadge(stock(8)); EarningsBadge(JSONObject())
        } } } }
        compose.onNodeWithText("E hoy").assertIsDisplayed()
        compose.onNodeWithText("E mañana").assertIsDisplayed()
        compose.onNodeWithText("E en 7 días").assertIsDisplayed()
        compose.onNodeWithText("E en 8 días").assertDoesNotExist()
    }
}
