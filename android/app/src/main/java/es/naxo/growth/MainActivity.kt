package es.naxo.growth

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.Article
import androidx.compose.material.icons.automirrored.outlined.ListAlt
import androidx.compose.material.icons.automirrored.outlined.TrendingUp
import androidx.compose.material.icons.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.core.view.WindowCompat
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import org.json.JSONObject
import java.time.Instant
import java.time.Duration
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

private val Spanish = Locale.forLanguageTag("es-ES")
private val Teal = Color(0xFF167B7D)
private val Mint = Color(0xFF87DDD0)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val model: GrowthViewModel = viewModel()
            val dark = when (model.appearance) { "dark" -> true; "light" -> false; else -> isSystemInDarkTheme() }
            SideEffect {
                WindowCompat.getInsetsController(window, window.decorView).apply {
                    isAppearanceLightStatusBars = !dark
                    isAppearanceLightNavigationBars = !dark
                }
            }
            GrowthTheme(dark) { GrowthApp(model) }
        }
    }
}

@Composable
fun GrowthTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val colors = if (dark) darkColorScheme(
        primary = Mint, onPrimary = Color(0xFF003738), primaryContainer = Color(0xFF234449), onPrimaryContainer = Color(0xFFB6ECE3),
        secondaryContainer = Color(0xFF234449), onSecondaryContainer = Color(0xFFB6ECE3),
        background = Color(0xFF101A23), onBackground = Color(0xFFE7EFF5), surface = Color(0xFF16232E), onSurface = Color(0xFFE7EFF5),
        surfaceVariant = Color(0xFF263744), onSurfaceVariant = Color(0xFFAEC0CF), outlineVariant = Color(0xFF304451)
    ) else lightColorScheme(
        primary = Teal, onPrimary = Color.White, primaryContainer = Color(0xFFE0F1EE), onPrimaryContainer = Color(0xFF165A5A),
        secondaryContainer = Color(0xFFE0F1EE), onSecondaryContainer = Color(0xFF165A5A),
        background = Color(0xFFF4F7FA), onBackground = Color(0xFF192D3D), surface = Color.White, onSurface = Color(0xFF192D3D),
        surfaceVariant = Color(0xFFE7EEF3), onSurfaceVariant = Color(0xFF667B8D), outlineVariant = Color(0xFFDCE6EE)
    )
    MaterialTheme(colorScheme = colors, typography = Typography(
        headlineLarge = Typography().headlineLarge.copy(fontWeight = FontWeight.Medium, letterSpacing = (-1).sp),
        headlineMedium = Typography().headlineMedium.copy(fontWeight = FontWeight.Medium, letterSpacing = (-.7).sp),
        titleLarge = Typography().titleLarge.copy(fontWeight = FontWeight.Medium),
        titleMedium = Typography().titleMedium.copy(fontWeight = FontWeight.Medium)
    ), content = content)
}

private enum class Tab(val title: String, val icon: ImageVector) {
    Home("Inicio", Icons.Outlined.Home), Changes("Cambios", Icons.Outlined.Insights),
    Reports("Informes", Icons.AutoMirrored.Outlined.Article), Table("Tabla", Icons.AutoMirrored.Outlined.ListAlt)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GrowthApp(model: GrowthViewModel) {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var symbol by rememberSaveable { mutableStateOf<String?>(null) }
    var settings by remember { mutableStateOf(false) }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(model.connected) {
        if (model.connected && !model.localEdition) lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            model.refresh()
            while (true) {
                val seconds = snapshotFlow { model.dashboard?.market?.num("poll_after_seconds") }
                    .first { it != null }!!.toLong().coerceIn(15, 3600)
                delay(seconds * 1000)
                model.refresh()
            }
        }
    }
    LaunchedEffect(symbol) { symbol?.let(model::openReport) }
    BackHandler(symbol != null) { symbol = null }
    if (!model.connected) {
        ConnectScreen(model)
        return
    }
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            TopAppBar(
                title = {
                    if (symbol != null) Text(symbol!!, style = MaterialTheme.typography.titleLarge)
                    else Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(11.dp)) {
                        Box(Modifier.size(38.dp).clip(RoundedCornerShape(12.dp)).background(MaterialTheme.colorScheme.primaryContainer), contentAlignment = Alignment.Center) {
                            Icon(Icons.AutoMirrored.Outlined.TrendingUp, null, tint = MaterialTheme.colorScheme.primary)
                        }
                        Column { Text("MI CARTERA", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, letterSpacing = 1.5.sp); Text("Growth", style = MaterialTheme.typography.titleLarge) }
                    }
                },
                navigationIcon = { if (symbol != null) IconButton(onClick = { symbol = null }) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, "Volver") } },
                actions = {
                    if (symbol == null) {
                        IconButton(onClick = model::refresh, enabled = !model.busy && !model.localEdition) {
                            if (model.busy) CircularProgressIndicator(Modifier.size(19.dp), strokeWidth = 2.dp) else Icon(Icons.Outlined.Refresh, "Actualizar datos")
                        }
                        IconButton(onClick = { settings = true }) { Icon(Icons.Outlined.Settings, "Ajustes") }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background)
            )
        },
        bottomBar = {
            if (symbol == null) NavigationBar(containerColor = MaterialTheme.colorScheme.surface, tonalElevation = 0.dp) {
                Tab.entries.forEachIndexed { index, item -> NavigationBarItem(selected = tab == index, onClick = { tab = index }, icon = { Icon(item.icon, null) }, label = { Text(item.title) }) }
            }
        }
    ) { padding ->
        val modifier = Modifier.padding(padding).fillMaxSize()
        if (symbol != null) ReportScreen(symbol!!, model, modifier)
        else Column(modifier) {
            if (model.error != null || model.offline) StatusBanner(model.error ?: if (model.localEdition) "Edición local · datos incluidos con esta APK" else "Mostrando la última copia guardada", model.dashboard?.asOf)
            val data = model.dashboard
            if (data == null) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    if (model.busy) Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(16.dp)) { CircularProgressIndicator(); Text("Leyendo tus datos publicados…") }
                    else EmptyState("No se pudieron cargar los datos", "Pulsa actualizar para volver a intentarlo.", Icons.Outlined.CloudOff)
                }
            } else {
                when (Tab.entries[tab]) {
                    Tab.Home -> HomeScreen(data, onReport = { symbol = it })
                    Tab.Changes -> ChangesScreen(data) { symbol = it }
                    Tab.Reports -> ReportsScreen(data) { symbol = it }
                    Tab.Table -> TableScreen(data) { symbol = it }
                }
            }
        }
    }
    if (settings) AlertDialog(
        onDismissRequest = { settings = false }, title = { Text("Tu Growth") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Apariencia", style = MaterialTheme.typography.titleSmall)
                listOf("system" to "Del dispositivo", "light" to "Clara", "dark" to "Oscura").forEach { (key, name) ->
                    Row(Modifier.fillMaxWidth().clickable { model.changeAppearance(key) }, verticalAlignment = Alignment.CenterVertically) { RadioButton(model.appearance == key, { model.changeAppearance(key) }); Text(name) }
                }
                HorizontalDivider()
                Text(if (model.localEdition) "Esta edición contiene una fotografía verificada de tus datos. La actualización automática requiere activar la API privada." else "La app consulta los datos publicados por Mercado al abrir y sigue la próxima consulta indicada por la API mientras está en primer plano. Los informes se renuevan cuando el sistema publica un análisis.", style = MaterialTheme.typography.bodySmall)
                Text("Growth ${BuildConfig.VERSION_NAME} · Solo lectura", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        },
        confirmButton = { TextButton(onClick = { settings = false }) { Text("Listo") } },
        dismissButton = { if (!model.localEdition) TextButton(onClick = { settings = false; symbol = null; model.disconnect() }, enabled = !model.busy) { Text("Desconectar") } }
    )
}

@Composable
private fun ConnectScreen(model: GrowthViewModel) {
    var code by rememberSaveable { mutableStateOf("") }
    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.safeDrawingPadding().imePadding().verticalScroll(rememberScrollState()).padding(horizontal = 28.dp, vertical = 36.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
            Box(Modifier.size(72.dp).clip(RoundedCornerShape(24.dp)).background(Brush.linearGradient(listOf(Color(0xFF173B4E), Color(0xFF235E62)))), contentAlignment = Alignment.Center) {
                Icon(Icons.AutoMirrored.Outlined.TrendingUp, null, Modifier.size(38.dp), tint = Mint)
            }
            Text("Tu cartera.\nCon perspectiva.", style = MaterialTheme.typography.headlineLarge)
            Text("Mercado, cambios e informes en un solo lugar.", style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            listOf(Icons.Outlined.Insights to "Lo que cambió en cada análisis", Icons.AutoMirrored.Outlined.Article to "Tus informes completos", Icons.Outlined.CloudDone to "Una copia siempre disponible").forEach { (icon, label) ->
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) { Icon(icon, null, tint = MaterialTheme.colorScheme.primary); Text(label, style = MaterialTheme.typography.bodyMedium) }
            }
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(code, { code = it }, Modifier.fillMaxWidth(), label = { Text("Código privado de acceso") }, singleLine = true, visualTransformation = PasswordVisualTransformation(), shape = RoundedCornerShape(16.dp), enabled = !model.busy)
            Text("Introduce el código entregado con la app. Solo lo necesitarás la primera vez.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            Button(onClick = { model.connect(code) }, enabled = code.trim().length >= 24 && !model.busy, modifier = Modifier.fillMaxWidth().height(54.dp), shape = RoundedCornerShape(16.dp)) {
                if (model.busy) { CircularProgressIndicator(Modifier.size(18.dp), color = MaterialTheme.colorScheme.onPrimary, strokeWidth = 2.dp); Spacer(Modifier.width(10.dp)); Text("Conectando…") } else Text("Entrar en Growth")
            }
            Text("Datos reales de tu sistema · Acceso de lectura", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun StatusBanner(message: String, at: String? = null) {
    Row(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.secondaryContainer).padding(14.dp), horizontalArrangement = Arrangement.spacedBy(9.dp)) {
        Icon(Icons.Outlined.Info, null, Modifier.size(18.dp))
        Column { Text(message, style = MaterialTheme.typography.bodySmall); if (!at.isNullOrBlank()) Text("Copia: ${dateTime(at)}", style = MaterialTheme.typography.labelSmall) }
    }
}

@Composable
private fun PageTitle(eyebrow: String, title: String, detail: String = "") {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(eyebrow.uppercase(Spanish), style = MaterialTheme.typography.labelSmall, letterSpacing = 1.2.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(title, style = MaterialTheme.typography.headlineMedium)
        if (detail.isNotBlank()) Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
internal fun HomeScreen(data: Dashboard, onReport: (String) -> Unit) {
    var allNews by rememberSaveable { mutableStateOf(false) }
    LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { PageTitle(LocalDate.now().format(DateTimeFormatter.ofPattern("EEEE, d MMM", Spanish)), "Tu mercado, de un vistazo") }
        item {
            Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(24.dp)).background(Brush.linearGradient(listOf(Color(0xFF173B4E), Color(0xFF235B63)))).padding(22.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("PULSO DEL MERCADO", color = Color(0xFFB0D7DB), style = MaterialTheme.typography.labelSmall, letterSpacing = 1.sp)
                    Icon(Icons.AutoMirrored.Outlined.TrendingUp, null, tint = Mint)
                }
                Text(data.market.str("risk_label").ifBlank { "Riesgo no disponible" }, color = Color.White, style = MaterialTheme.typography.titleLarge)
                data.market.num("risk_score")?.let { score -> LinearProgressIndicator(progress = { (score / 100).toFloat().coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth().height(5.dp).clip(CircleShape), color = Mint, trackColor = Color(0xFF3D626F)) }
                Text(data.market.str("vxn_label").ifBlank { "VXN no disponible" }, color = Color(0xFFC6DEE5), style = MaterialTheme.typography.bodySmall)
            }
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                MetricTile("QQQ hoy", pct(data.market.num("qqq_day")), Modifier.weight(1f), signedColor(data.market.num("qqq_day")))
                MetricTile("DD6M", pct(data.market.num("qqq_drawdown")), Modifier.weight(1f))
                MetricTile("VXN", decimal(data.market.num("vxn")), Modifier.weight(1f))
            }
        }
        item {
            val pullback = data.market.optJSONObject("qqq_pullback")
            val drawdown = pullback?.num("drawdown")
            Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surface) {
                Row(Modifier.fillMaxWidth().padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("Caída QQQ", style = MaterialTheme.typography.bodyMedium)
                    Text(pct(drawdown), style = MaterialTheme.typography.titleMedium)
                }
            }
        }
        item { SectionTitle("Noticias generales Growth", "Próximamente") }
        item {
            Surface(shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surface) {
                Row(Modifier.fillMaxWidth().padding(18.dp), horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Outlined.AutoAwesome, null, tint = MaterialTheme.colorScheme.primary)
                    Text("Aquí aparecerán las novedades generales que puedan afectar a tu cartera growth.", style = MaterialTheme.typography.bodyMedium)
                }
            }
        }
        item { SectionTitle("Titulares de tus empresas", "IBKR") }
        item { Text("Titulares recogidos al preparar los análisis; cada uno conserva su fecha.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        if (data.news.isEmpty()) item { EmptyState("Sin titulares recientes", "Los análisis publicados no contienen noticias IBKR recientes. Las noticias generales llegarán en una próxima versión.", Icons.Outlined.Newspaper) }
        items(if (allNews) data.news else data.news.take(6), key = { it.str("id") }) { news ->
            Surface(onClick = { onReport(news.str("symbol")) }, shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.surface) {
                Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        val count = news.optJSONArray("symbols")?.length() ?: 1
                        Tag(news.str("symbol") + if (count > 1) " +${count - 1}" else "")
                        Text(dateTime(news.str("at")), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Text(cleanMarkdown(news.str("title")), style = MaterialTheme.typography.titleSmall)
                    Text("${news.str("provider")} · Abrir análisis", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                }
            }
        }
        if (data.news.size > 6) item { TextButton(onClick = { allNews = !allNews }) { Text(if (allNews) "Ver menos titulares" else "Ver todos los titulares (${data.news.size})") } }
        if (data.warnings.isNotEmpty()) item { StatusBanner(data.warnings.joinToString("\n")) }
    }
}

@Composable
internal fun ChangesScreen(data: Dashboard, onReport: (String) -> Unit) {
    var expanded by rememberSaveable { mutableStateOf<String?>(null) }
    LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(13.dp)) {
        item { PageTitle("Últimos análisis", "Qué ha cambiado", "Catalizadores, próximos eventos, tesis y analistas relevantes.") }
        if (data.changes.isEmpty()) item { EmptyState("Sin novedades destacadas", "Los últimos informes no añaden cambios materiales.", Icons.Outlined.DoneAll) }
        items(data.changes, key = { it.str("id") }) { change ->
            val id = change.str("id")
            Surface(onClick = { expanded = if (expanded == id) null else id }, shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surface) {
                Column(Modifier.fillMaxWidth().padding(17.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(9.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(change.str("symbol"), style = MaterialTheme.typography.titleMedium)
                        val kind = change.str("kind")
                        val stamp = if (kind == "event" && change.str("event_date").isNotBlank()) {
                            "Previsto ${shortDate(change.str("event_date"))} · ${if (change.str("change_type") == "new") "nuevo" else "actualizado"}"
                        } else dateTime(change.str("at"))
                        Text(stamp, modifier = Modifier.weight(1f), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        val label = when (kind) {
                            "catalyst" -> when (change.str("change_type")) {
                                "updated" -> "Catalizador actualizado"
                                "removed" -> "Catalizador retirado"
                                else -> "Catalizador ${signedNumber(change.num("impact"))}"
                            }
                            "event" -> "Próximo evento"
                            "score" -> "Tesis"
                            "analyst" -> "Analistas"
                            else -> "Novedad"
                        }
                        Tag(label)
                    }
                    Text(cleanMarkdown(change.str("title")), style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.primary, maxLines = if (expanded == id) Int.MAX_VALUE else 2, overflow = TextOverflow.Ellipsis)
                    if (expanded == id) {
                        if (change.str("detail").isNotBlank()) Text(cleanMarkdown(change.str("detail")), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        TextButton(onClick = { onReport(change.str("symbol")) }, modifier = Modifier.align(Alignment.End)) { Text("Leer informe completo") }
                    }
                }
            }
        }
    }
}

@Composable
internal fun ReportsScreen(data: Dashboard, onReport: (String) -> Unit) {
    var query by rememberSaveable { mutableStateOf("") }
    var expanded by rememberSaveable { mutableStateOf<String?>(null) }
    val reports = data.stocks.filter { it.str("symbol").contains(query, true) || it.str("group").contains(query, true) }.sortedByDescending { it.str("analysis_at") }
    val latest = data.stocks.filter { it.str("analysis_status") == "ok" }.maxOfOrNull { it.str("analysis_at") }
    LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text("BIBLIOTECA", style = MaterialTheme.typography.labelSmall, letterSpacing = 1.2.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("Informes recientes", style = MaterialTheme.typography.titleMedium)
                Text(if (latest.isNullOrBlank()) "Aún no hay informes completos" else "Último informe completo · ${dateTime(latest)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        item { SearchBox(query, { query = it }) }
        if (reports.isEmpty()) item { EmptyState("Sin resultados", "Prueba con otro ticker o grupo.", Icons.Outlined.Search) }
        items(reports.chunked(3), key = { it.first().str("symbol") }) { row ->
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    row.forEach { stock ->
                        val ticker = stock.str("symbol")
                        Surface(onClick = { expanded = if (expanded == ticker) null else ticker }, modifier = Modifier.weight(1f), shape = RoundedCornerShape(12.dp), color = if (expanded == ticker) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.primaryContainer) {
                            Box(Modifier.height(48.dp), contentAlignment = Alignment.Center) {
                                Text(ticker, style = MaterialTheme.typography.titleSmall, color = if (expanded == ticker) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onPrimaryContainer)
                            }
                        }
                    }
                    repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
                }
                row.firstOrNull { it.str("symbol") == expanded }?.let { stock ->
                    val ticker = stock.str("symbol")
                    val decision = stock.obj("decision")
                    Surface(shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.surface) {
                        Column(Modifier.fillMaxWidth().padding(17.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text(ticker, style = MaterialTheme.typography.titleMedium)
                                Text(dateTime(stock.str("analysis_at")), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { Tag("Tesis ${score(decision, "thesis_score")}"); Tag("Setup ${decimal(decision.num("setup_score"))}") }
                            Text(cleanMarkdown(decision.str("narrative")).ifBlank { "No hay resumen disponible." }, style = MaterialTheme.typography.bodyMedium)
                            AttemptNote(stock)
                            Button(onClick = { onReport(ticker) }, enabled = stock.str("analysis_status") == "ok", shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) { Text("Leer informe completo") }
                        }
                    }
                }
            }
        }
    }
}

@Composable
internal fun TableScreen(data: Dashboard, onReport: (String) -> Unit) {
    var query by rememberSaveable { mutableStateOf("") }
    var filter by rememberSaveable { mutableStateOf("Todos") }
    var expanded by rememberSaveable { mutableStateOf<String?>(null) }
    var sort by rememberSaveable { mutableStateOf("Señal") }
    var menu by remember { mutableStateOf(false) }
    val session = data.market.str("session")
    val now = Instant.now()
    val signals = data.stocks.associate { it.str("symbol") to zoneSignal(it, session, data.market.num("refresh_interval_minutes"), now) }
    val stocks = sortedStocks(data.stocks.filter { stock ->
        val kind = signals[stock.str("symbol")]?.kind
        (filter == "Todos" || filter == "Cartera" && (stock.num("shots") ?: 0.0) > 0 || filter == "Compra" && kind == "buy" || filter == "Venta" && kind == "sell") &&
            (stock.str("symbol").contains(query, true) || stock.str("group").contains(query, true))
    }, sort, signals)
    LazyColumn(contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text("SEGUIMIENTO", style = MaterialTheme.typography.labelSmall, letterSpacing = 1.2.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("Mi tabla", style = MaterialTheme.typography.titleLarge)
                    Box {
                        TextButton(onClick = { menu = true }) { Icon(Icons.Outlined.Sort, null, Modifier.size(18.dp)); Spacer(Modifier.width(5.dp)); Text(sort) }
                        DropdownMenu(menu, { menu = false }) { listOf("Señal", "Tesis", "Setup", "Fuerza", "Día", "Ticker").forEach { option -> DropdownMenuItem(text = { Text(option) }, onClick = { sort = option; menu = false }) } }
                    }
                }
                val buyCount = signals.values.count { it.kind == "buy" }
                val sellCount = signals.values.count { it.kind == "sell" }
                val summary = if (session == "closed" || session.isBlank()) "Último precio: $buyCount compra · $sellCount venta · ${data.stocks.size} tickers"
                    else "${signals.values.count { it.kind == "buy" && it.live }} compra · ${signals.values.count { it.kind == "sell" && it.live }} venta ahora · ${buyCount + sellCount - signals.values.count { it.live }} con precio anterior"
                Text(summary, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("Cotizaciones ${sessionLabel(session)} · datos publicados por Mercado", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        item { SearchBox(query, { query = it }) }
        item {
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("Todos", "Compra", "Venta", "Cartera").forEach { choice -> FilterChip(filter == choice, { filter = choice }, label = { Text(choice) }) }
            }
        }
        if (stocks.isEmpty()) item { EmptyState("Sin resultados", "Cambia el filtro o la búsqueda.", Icons.Outlined.Search) }
        items(stocks, key = { it.str("symbol") }) { stock ->
            val symbol = stock.str("symbol")
            StockCard(stock, signals[symbol] ?: ZoneSignal(), expanded == symbol, { expanded = if (expanded == symbol) null else symbol }, onReport)
        }
    }
}

internal data class ZoneSignal(val kind: String = "none", val label: String = "", val live: Boolean = false, val rank: Int = 9)

internal fun zoneSignal(stock: JSONObject, session: String, intervalMinutes: Double?, now: Instant = Instant.now()): ZoneSignal {
    val price = stock.num("price")?.takeIf { it > 0 } ?: return ZoneSignal()
    val quoteAt = runCatching { Instant.parse(stock.str("quote_at")) }.getOrNull()
    val age = quoteAt?.let { Duration.between(it, now).seconds }
    val live = session != "closed" && session.isNotBlank() && age != null && age in -60..((intervalMinutes ?: 1.0).toLong() * 120 + 60)
    fun inside(zone: JSONObject): Boolean {
        val lower = zone.num("lower") ?: return false
        val upper = zone.num("upper") ?: return false
        return lower <= upper && price >= lower && price <= upper
    }
    val plan = stock.obj("plan")
    val held = (stock.num("shots") ?: 0.0) > 0
    val base = when {
        held && inside(plan.obj("resistance")) -> "sell" to "Resistencia"
        inside(plan.obj("ambitious_entry")) -> "buy" to "Washout"
        inside(plan.obj("entry")) -> "buy" to "Entrada"
        else -> return ZoneSignal()
    }
    val label = if (live) (if (base.first == "sell") "Zona de venta" else "Zona de compra") + " · ${base.second}"
        else "Último precio en ${base.second.lowercase(Spanish)}"
    return ZoneSignal(base.first, label, live, if (live) { if (base.first == "buy") 0 else 1 } else { if (base.first == "buy") 2 else 3 })
}

private fun sessionLabel(session: String): String = when (session) {
    "regular" -> "en sesión"
    "pre-market" -> "en premercado"
    "post-market" -> "en posmercado"
    "closed" -> "con mercado cerrado"
    else -> "según última lectura"
}

internal fun sortedStocks(stocks: List<JSONObject>, sort: String, signals: Map<String, ZoneSignal> = emptyMap()): List<JSONObject> {
    if (sort == "Señal") return stocks.sortedWith(compareBy<JSONObject> { signals[it.str("symbol")]?.rank ?: 9 }.thenBy { it.str("symbol") })
    if (sort == "Ticker") return stocks.sortedBy { it.str("symbol") }
    fun key(stock: JSONObject): Double? = when (sort) { "Tesis" -> stock.obj("decision").num("thesis_score"); "Setup" -> stock.obj("decision").num("setup_score"); "Fuerza" -> stock.num("strength"); else -> stock.num("day_change") }
    return stocks.sortedWith(compareByDescending<JSONObject> { key(it) ?: Double.NEGATIVE_INFINITY }.thenBy { it.str("symbol") })
}

@Composable
private fun StockCard(stock: JSONObject, signal: ZoneSignal, expanded: Boolean, onToggle: () -> Unit, onReport: (String) -> Unit) {
    val decision = stock.obj("decision")
    val plan = stock.obj("plan")
    val ticker = stock.str("symbol")
    Surface(onClick = onToggle, shape = RoundedCornerShape(20.dp), color = MaterialTheme.colorScheme.surface) {
        Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(ticker, style = MaterialTheme.typography.titleMedium)
                    val shots = stock.num("shots")?.toInt() ?: 0
                    Text(stock.str("group") + if (shots > 0) " · $shots shot${if (shots > 1) "s" else ""}" else "", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    EarningsBadge(stock)
                }
                Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(money(stock.num("price")), style = MaterialTheme.typography.titleMedium)
                    Text(pct(stock.num("day_change")), color = signedColor(stock.num("day_change")), style = MaterialTheme.typography.labelSmall)
                }
            }
            if (signal.kind != "none") {
                val color = if (!signal.live) MaterialTheme.colorScheme.surfaceVariant else if (signal.kind == "sell") MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.primaryContainer
                val ink = if (!signal.live) MaterialTheme.colorScheme.onSurfaceVariant else if (signal.kind == "sell") MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onPrimaryContainer
                Text(signal.label, Modifier.clip(RoundedCornerShape(8.dp)).background(color).padding(horizontal = 9.dp, vertical = 5.dp), style = MaterialTheme.typography.labelMedium, color = ink)
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Tesis ${score(decision, "thesis_score")} · Setup ${decimal(decision.num("setup_score"))} · Fuerza ${decimal(stock.num("strength"))}/10", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text("Precio ${dateTime(stock.str("quote_at"))}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (expanded) {
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = .65f))
                Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                    LevelTile("Entrada", plan.obj("entry"), plan.num("entry_strength_score"), stock.num("price"), Modifier.weight(1f))
                    LevelTile("Washout", plan.obj("ambitious_entry"), plan.num("washout_strength_score"), stock.num("price"), Modifier.weight(1f))
                    LevelTile("Resistencia", plan.obj("resistance"), plan.num("resistance_strength_score"), stock.num("price"), Modifier.weight(1f), resistance = true)
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    SmallStat("5d", pct(stock.num("return_5d")))
                    SmallStat("20d", pct(stock.num("return_20d")))
                    SmallStat("DD6M", pct(stock.num("drawdown")))
                }
                Text("Análisis ${dateTime(stock.str("analysis_at"))}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                earningsDisplay(stock)?.let { Text(it.detail, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                AttemptNote(stock)
                Button(onClick = { onReport(ticker) }, enabled = stock.str("analysis_status") == "ok", shape = RoundedCornerShape(12.dp), modifier = Modifier.fillMaxWidth()) { Text("Leer informe completo") }
            }
        }
    }
}

@Composable
internal fun EarningsBadge(stock: JSONObject) {
    val display = earningsDisplay(stock) ?: return
    val dark = MaterialTheme.colorScheme.surface.luminance() < .5f
    val ink = if (display.urgent) { if (dark) Color(0xFFFF8A80) else Color(0xFFD93025) }
        else { if (dark) Color(0xFFFFB74D) else Color(0xFFAA6100) }
    Text(display.label, Modifier.border(if (display.urgent) 2.dp else 1.dp, ink, RoundedCornerShape(6.dp))
        .padding(horizontal = 6.dp, vertical = 3.dp), color = ink, style = MaterialTheme.typography.labelSmall)
}

@Composable
private fun LevelTile(label: String, range: JSONObject, strength: Double?, price: Double?, modifier: Modifier, resistance: Boolean = false) {
    val low = range.num("lower"); val high = range.num("upper")
    val inside = low != null && high != null && price != null && price >= low && price <= high
    val color = if (inside) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.background
    val border = if (strength != null && strength >= 85) MaterialTheme.colorScheme.primary else Color.Transparent
    Column(modifier.clip(RoundedCornerShape(12.dp)).background(color).border(1.dp, border, RoundedCornerShape(12.dp)).padding(9.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(rangeLabel(range), style = MaterialTheme.typography.labelMedium, lineHeight = 18.sp)
        Text(if (strength == null) "Sin fuerza" else "${strength.toInt()}/100", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
        if (inside) Text(if (resistance) "En zona" else "Dentro", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
    }
}

@Composable
private fun AttemptNote(stock: JSONObject) {
    if (stock.str("attempt_notice").isNotBlank()) Text(stock.str("attempt_notice"), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
    else if (stock.str("last_attempt_status") == "failed") Text("Último intento fallido · se conserva el informe del ${dateTime(stock.str("analysis_at"))}", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
    else if (stock.str("last_attempt_status") == "unavailable") Text("No se pudo verificar el último intento.", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
}

@Composable
private fun ReportScreen(symbol: String, model: GrowthViewModel, modifier: Modifier) {
    val report = model.report?.takeIf { it.str("symbol") == symbol }
    if (report == null) {
        Box(modifier, contentAlignment = Alignment.Center) {
            if (model.reportBusy) CircularProgressIndicator()
            else Column(horizontalAlignment = Alignment.CenterHorizontally) { EmptyState("Informe no disponible", model.reportError ?: "No hay un informe válido publicado.", Icons.AutoMirrored.Outlined.Article); TextButton(onClick = { model.openReport(symbol) }) { Text("Reintentar") } }
        }
        return
    }
    val blocks = remember(report) { report.str("analysis_markdown").split(Regex("\\n\\s*\\n")) }
    LazyColumn(modifier, contentPadding = PaddingValues(22.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        item { PageTitle("Informe completo", symbol, "Publicado ${dateTime(report.str("generated_at"))}") }
        if (model.reportBusy) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
        if (model.reportOffline) item { StatusBanner("Copia guardada del informe", report.str("generated_at")) }
        model.reportError?.let { error -> item { Text(error, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) } }
        if (report.str("attempt_notice").isNotBlank()) item { StatusBanner(report.str("attempt_notice"), report.str("last_attempt_at")) }
        else if (report.str("last_attempt_status") == "failed") item { StatusBanner("El último intento falló. Este es el último informe válido.", report.str("generated_at")) }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                MetricTile("Tesis", score(report.obj("decision"), "thesis_score"), Modifier.weight(1f))
                MetricTile("Setup", decimal(report.obj("decision").num("setup_score")), Modifier.weight(1f))
            }
        }
        items(blocks.size) { index ->
            val block = blocks[index].trim()
            if (block.isNotBlank() && !block.matches(Regex("[-*_]{3,}"))) {
                val heading = block.startsWith("#")
                SelectionContainer {
                    Text(markdownText(block.removePrefix("### ").removePrefix("## ").removePrefix("# ")),
                        style = if (heading) MaterialTheme.typography.titleLarge else MaterialTheme.typography.bodyMedium,
                        lineHeight = if (heading) 29.sp else 24.sp)
                }
            }
        }
        item { Spacer(Modifier.height(20.dp)) }
    }
}

@Composable
private fun SearchBox(query: String, onChange: (String) -> Unit) {
    OutlinedTextField(query, onChange, Modifier.fillMaxWidth(), placeholder = { Text("Ticker o grupo") }, leadingIcon = { Icon(Icons.Outlined.Search, null) }, singleLine = true, shape = RoundedCornerShape(16.dp))
}

@Composable
private fun MetricTile(label: String, value: String, modifier: Modifier, color: Color = MaterialTheme.colorScheme.onSurface) {
    Surface(modifier, shape = RoundedCornerShape(17.dp), color = MaterialTheme.colorScheme.surface) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(value, style = MaterialTheme.typography.titleLarge, fontSize = 20.sp, color = color, maxLines = 1)
        }
    }
}

@Composable
private fun SectionTitle(title: String, caption: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) { Text(title, style = MaterialTheme.typography.titleMedium); Text(caption, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
}

@Composable
private fun SmallStat(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) { Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant); Text(value, style = MaterialTheme.typography.labelLarge) }
}

@Composable
private fun Tag(label: String) {
    Text(label, Modifier.clip(RoundedCornerShape(7.dp)).background(MaterialTheme.colorScheme.primaryContainer).padding(horizontal = 8.dp, vertical = 4.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onPrimaryContainer)
}

@Composable
private fun SymbolAvatar(symbol: String) {
    Box(Modifier.size(46.dp).clip(RoundedCornerShape(15.dp)).background(MaterialTheme.colorScheme.primaryContainer), contentAlignment = Alignment.Center) { Text(symbol.take(4), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onPrimaryContainer) }
}

@Composable
private fun EmptyState(title: String, detail: String, icon: ImageVector) {
    Column(Modifier.fillMaxWidth().padding(vertical = 32.dp, horizontal = 15.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Icon(icon, null, Modifier.size(34.dp), tint = MaterialTheme.colorScheme.primary)
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun signedColor(number: Double?): Color = when { number == null || number == 0.0 -> MaterialTheme.colorScheme.onSurfaceVariant; number > 0 -> MaterialTheme.colorScheme.primary; else -> MaterialTheme.colorScheme.error }

fun decimal(value: Double?, digits: Int = 1): String = value?.let { String.format(Spanish, "%.${digits}f", it).removeSuffix(",0") } ?: "—"
fun money(value: Double?): String = value?.let { "${decimal(it, 2)} $" } ?: "—"
fun pct(value: Double?): String = value?.let {
    val percent = it * 100
    if (percent != 0.0 && kotlin.math.abs(percent) < .01) (if (percent > 0) "+" else "−") + "<0,01 %"
    else (if (percent > 0) "+" else "") + decimal(percent, 2) + " %"
} ?: "—"
fun signedNumber(value: Double?): String = value?.let { (if (it > 0) "+" else "") + decimal(it) } ?: "—"
fun score(decision: JSONObject, key: String): String = decimal(decision.num(key))
fun rangeLabel(value: JSONObject): String {
    val low = value.num("lower") ?: return "—"
    val high = value.num("upper") ?: return "—"
    return if (low == high) "${decimal(low, 2)} $" else "${decimal(low, 2)} $\na ${decimal(high, 2)} $"
}
fun dateTime(value: String): String {
    if (value.isBlank()) return "Fecha no disponible"
    return runCatching { Instant.parse(value).atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("d MMM · HH:mm", Spanish)) }.getOrElse { value.replace('T', ' ').take(19) }
}
fun shortDate(value: String): String = runCatching { LocalDate.parse(value.take(10)).format(DateTimeFormatter.ofPattern("d MMM", Spanish)) }.getOrElse { value.take(10) }
fun cleanMarkdown(value: String): String = value.replace(Regex("\\[([^]]+)]\\([^)]*\\)"), "$1").replace("**", "").replace("`", "")
fun markdownText(value: String): AnnotatedString = buildAnnotatedString {
    val plainLinks = value.replace(Regex("\\[([^]]+)]\\([^)]*\\)"), "$1").replace(Regex("(?m)^[-*] "), "• ").replace("`", "")
    var start = 0
    Regex("\\*\\*(.+?)\\*\\*").findAll(plainLinks).forEach { match ->
        append(plainLinks.substring(start, match.range.first))
        pushStyle(SpanStyle(fontWeight = FontWeight.Medium)); append(match.groupValues[1]); pop()
        start = match.range.last + 1
    }
    append(plainLinks.substring(start))
}
