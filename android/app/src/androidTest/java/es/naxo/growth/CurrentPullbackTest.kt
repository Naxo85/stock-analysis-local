package es.naxo.growth

import androidx.compose.material3.Surface
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollTo
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test

class CurrentPullbackTest {
    @get:Rule val compose = createComposeRule()
    @Test fun currentEpisodeHasItsOwnDatedClose() {
        val pullback = JSONObject().put("drawdown", -.0656).put("state", "Episodio abierto")
            .put("threshold_label", "Umbral −5%: 721,68 $")
            .put("peak_label", "Máximo: 759,66 $ · 06/10/2026")
            .put("close_label", "Cierre: 709,80 $ · 16/10/2026")
            .put("basis", "Cierres diarios · reinicio tras rebote del 5%")
        val dashboard = Dashboard(JSONObject().put("market", JSONObject().put("qqq_pullback", pullback)))
        compose.setContent { GrowthTheme(false) { Surface { HomeScreen(dashboard) {} } } }
        compose.onNodeWithText("Caída QQQ").performScrollTo().assertIsDisplayed()
        compose.onNodeWithText("Cierre: 709,80 $ · 16/10/2026").assertDoesNotExist()
        compose.onNodeWithText("Episodios en 2026").assertDoesNotExist()
    }
}
