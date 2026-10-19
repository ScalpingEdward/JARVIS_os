// Languages: the page is written in German; this swaps every text and label for English, Spanish,
// Russian or Arabic (right to left). The choice comes from ?lang=, then the visitor's last choice,
// then the browser's language -- and English for everyone else.
(() => {
  const LANGS = { en: 'English', es: 'Español', ru: 'Русский', de: 'Deutsch', ar: 'العربية' };
  // German text -> [en, es, ru, ar]
  const T = {
    'Vorteile': ['Benefits', 'Ventajas', 'Преимущества', 'المزايا'],
    'Manager': ['Managers', 'Gestores', 'Модули', 'المديرون'],
    'Kontrolle': ['Control', 'Control', 'Контроль', 'التحكم'],
    'Preise': ['Pricing', 'Precios', 'Цены', 'الأسعار'],
    'Voraussetzungen': ['Requirements', 'Requisitos', 'Требования', 'المتطلبات'],
    'Pakete ansehen': ['See plans', 'Ver planes', 'Смотреть тарифы', 'عرض الباقات'],
    'Dein digitales Büro mit Assistent': ['Your digital office with an assistant', 'Tu oficina digital con asistente', 'Твой цифровой офис с ассистентом', 'مكتبك الرقمي مع مساعد'],
    'Vorheriger Look': ['Previous look', 'Estilo anterior', 'Предыдущий стиль', 'المظهر السابق'],
    'Nächster Look': ['Next look', 'Siguiente estilo', 'Следующий стиль', 'المظهر التالي'],
    'Weniger Routine.': ['Less routine.', 'Menos rutina.', 'Меньше рутины.', 'روتين أقل.'],
    'Mehr Zeit für dich.': ['More time for you.', 'Más tiempo para ti.', 'Больше времени для тебя.', 'وقت أكثر لك.'],
    'Dein All-in-One-Dashboard: Trading, Instagram, Postfach und mehr – zusammengestellt, wie du es brauchst.': [
      'Your all-in-one dashboard: trading, Instagram, inbox and more – put together the way you need it.',
      'Tu panel todo en uno: trading, Instagram, correo y más – armado como lo necesitas.',
      'Твой дашборд «всё в одном»: трейдинг, Instagram, почта и многое другое – собран так, как нужно тебе.',
      'لوحة التحكم الشاملة لك: التداول وإنستغرام والبريد والمزيد – مجمّعة كما تحتاجها.'],
    'Trading': ['Trading', 'Trading', 'Трейдинг', 'التداول'],
    '12 Signale kopiert': ['12 signals copied', '12 señales copiadas', '12 сигналов скопировано', 'تم نسخ 12 إشارة'],
    'Stops nachgezogen': ['Stops trailed', 'Stops ajustados', 'Стопы подтянуты', 'تم تحريك الوقف'],
    'Heute': ['Today', 'Hoy', 'Сегодня', 'اليوم'],
    'wichtige Mails': ['important emails', 'correos importantes', 'важных писем', 'رسائل مهمة'],
    '1 Reel bereit': ['1 reel ready', '1 reel listo', '1 Reel готов', 'ريل واحد جاهز'],
    'Weniger Aufwand. Mehr Freiraum.': ['Less effort. More freedom.', 'Menos esfuerzo. Más libertad.', 'Меньше усилий. Больше свободы.', 'جهد أقل. حرية أكثر.'],
    'Dein All-in-One-Dashboard: Du stellst es aus den Managern zusammen, die du brauchst – Trading, Instagram, Postfach und mehr. AURON übernimmt die wiederkehrenden Aufgaben dahinter. Du legst die Regeln fest und gewinnst Zeit für dein Business und dein Leben.': [
      'Your all-in-one dashboard: build it from the managers you need – trading, Instagram, inbox and more. AURON takes over the repetitive work behind them. You set the rules and win back time for your business and your life.',
      'Tu panel todo en uno: lo armas con los gestores que necesitas – trading, Instagram, correo y más. AURON se encarga del trabajo repetitivo. Tú pones las reglas y recuperas tiempo para tu negocio y tu vida.',
      'Твой дашборд «всё в одном»: собери его из нужных модулей – трейдинг, Instagram, почта и другое. AURON берёт на себя рутину. Ты задаёшь правила и возвращаешь время для бизнеса и жизни.',
      'لوحتك الشاملة: تبنيها من المديرين الذين تحتاجهم – التداول وإنستغرام والبريد والمزيد. يتولى AURON المهام المتكررة خلفها. أنت تضع القواعد وتستعيد وقتك لعملك وحياتك.'],
    'Deine Vorteile entdecken': ['Discover the benefits', 'Descubre las ventajas', 'Узнать преимущества', 'اكتشف المزايا'],
    'Dashboard entdecken': ['Explore the dashboard', 'Explora el panel', 'Посмотреть дашборд', 'استكشف اللوحة'],
    'So kann dein Tag aussehen': ['What your day can look like', 'Así puede ser tu día', 'Так может выглядеть твой день', 'هكذا قد يبدو يومك'],
    'Signale aus 3 Gruppen kopiert, Stops nachgezogen': ['signals from 3 groups copied, stops trailed', 'señales de 3 grupos copiadas, stops ajustados', 'сигналов из 3 групп скопировано, стопы подтянуты', 'إشارة من 3 مجموعات، مع تحريك الوقف'],
    'wichtige Mails priorisiert, 41 Werbemails sortiert': ['important emails first, 41 promos sorted out', 'correos importantes primero, 41 promociones apartadas', 'важных письма вперёд, 41 рекламное убрано', 'رسائل مهمة أولاً، و41 رسالة إعلانية مفروزة'],
    'Reel geschnitten und zur Freigabe bereit': ['reel cut and ready for approval', 'reel editado y listo para aprobar', 'Reel смонтирован и ждёт одобрения', 'ريل مقصوص وجاهز للموافقة'],
    'Inflationsdaten – Warnung 30 Min vorher': ['inflation data – alert 30 min ahead', 'datos de inflación – aviso 30 min antes', 'данные по инфляции – сигнал за 30 мин', 'بيانات التضخم – تنبيه قبل 30 دقيقة'],
    'Weniger Handgriffe. Mehr Zeit.': ['Fewer clicks. More time.', 'Menos clics. Más tiempo.', 'Меньше действий. Больше времени.', 'نقرات أقل. وقت أكثر.'],
    'Deine Vorteile': ['Benefits', 'Ventajas', 'Преимущества', 'المزايا'],
    'Routine automatisieren. Zeit zurückgewinnen.': ['Automate routine. Win back time.', 'Automatiza la rutina. Recupera tiempo.', 'Автоматизируй рутину. Верни время.', 'أتمت الروتين. استعد وقتك.'],
    'Dein Assistent läuft auf deinem Rechner': ['Your assistant runs on your own machine', 'Tu asistente funciona en tu equipo', 'Ассистент работает на твоём компьютере', 'مساعدك يعمل على جهازك'],
    'Deine Regeln. Deine Freigaben. Deine Kontrolle.': ['Your rules. Your approvals. Your control.', 'Tus reglas. Tus aprobaciones. Tu control.', 'Твои правила. Твои решения. Твой контроль.', 'قواعدك. موافقاتك. تحكّمك.'],
    'Wie AURON dir konkret hilft.': ['How AURON actually helps you.', 'Cómo te ayuda AURON en concreto.', 'Как именно AURON тебе помогает.', 'كيف يساعدك AURON فعلياً.'],
    'Kein weiteres Tool, das du bedienen musst – sondern ein System, das die Arbeit für dich erledigt. Vier Beispiele.': [
      'Not another tool to operate – a system that does the work for you. Four examples.',
      'No es otra herramienta que manejar – es un sistema que hace el trabajo por ti. Cuatro ejemplos.',
      'Не ещё один инструмент, которым надо управлять, а система, которая работает за тебя. Четыре примера.',
      'ليست أداة أخرى عليك تشغيلها – بل نظام يقوم بالعمل عنك. أربعة أمثلة.'],
    'Social Media': ['Social media', 'Redes sociales', 'Соцсети', 'وسائل التواصل'],
    'in deinem Look. Automatisch.': ['in your look. Automatically.', 'con tu estilo. Automático.', 'в твоём стиле. Автоматически.', 'بأسلوبك. تلقائياً.'],
    'Du lädst Fotos und Videos einfach in deinen Drive-Ordner. Alles Weitere übernimmt AURON – bis zum fertigen Post, den du nur noch freigibst.': [
      'You just drop photos and videos into your Drive folder. AURON does the rest – right up to the finished post you only approve.',
      'Solo subes fotos y vídeos a tu carpeta de Drive. AURON hace el resto – hasta el post terminado que solo apruebas.',
      'Просто загружаешь фото и видео в папку Drive. Остальное делает AURON – до готового поста, который тебе нужно только одобрить.',
      'تضع الصور والفيديوهات في مجلد Drive فقط. ويتولى AURON الباقي – حتى المنشور الجاهز الذي توافق عليه فقط.'],
    'Statt Stunden mit Sortieren, Bearbeiten und Schneiden: ein Tipp auf „Freigeben“.': [
      'Instead of hours of sorting, editing and cutting: one tap on “Approve”.',
      'En lugar de horas ordenando, editando y cortando: un toque en «Aprobar».',
      'Вместо часов сортировки, обработки и монтажа – одно нажатие «Одобрить».',
      'بدلاً من ساعات من الفرز والتعديل والقص: نقرة واحدة على «موافقة».'],
    'Dein Look, automatisch': ['Your look, automatically', 'Tu estilo, automático', 'Твой стиль – автоматически', 'أسلوبك تلقائياً'],
    'Holt Fotos und Videos aus deinem Drive und bearbeitet sie nach deinem Preset.': ['Pulls photos and videos from your Drive and edits them with your preset.', 'Toma fotos y vídeos de tu Drive y los edita con tu preset.', 'Берёт фото и видео из Drive и обрабатывает по твоему пресету.', 'يجلب الصور والفيديوهات من Drive ويعدّلها بإعداداتك.'],
    'Kennt deinen Account': ['Knows your account', 'Conoce tu cuenta', 'Знает твой аккаунт', 'يعرف حسابك'],
    'Einmal Charakter und Stil beschreiben – jede Caption klingt nach dir.': ['Describe your character and style once – every caption sounds like you.', 'Describe tu carácter y estilo una vez – cada caption suena a ti.', 'Один раз опиши характер и стиль – каждая подпись звучит как ты.', 'صف شخصيتك وأسلوبك مرة واحدة – وكل تعليق سيبدو بصوتك.'],
    'Wählt die besten aus': ['Picks the best', 'Elige las mejores', 'Выбирает лучшее', 'يختار الأفضل'],
    'Jedes Foto bekommt einen Score, die stärksten tragen den Post.': ['Every photo gets a score; the strongest carry the post.', 'Cada foto recibe una puntuación; las mejores llevan el post.', 'Каждое фото получает оценку, лучшие идут в пост.', 'كل صورة تحصل على تقييم، والأقوى تتصدّر المنشور.'],
    'Schneidet und plant': ['Cuts and schedules', 'Edita y programa', 'Монтирует и планирует', 'يقص ويجدول'],
    'Reels im richtigen Format, ein Post pro Tag, nie zweimal dasselbe Thema.': ['Reels in the right format, one post a day, never the same topic twice.', 'Reels en el formato correcto, un post al día, nunca el mismo tema dos veces.', 'Reels в нужном формате, один пост в день, без повторов темы.', 'ريلز بالصيغة الصحيحة، منشور واحد يومياً، دون تكرار الموضوع.'],
    'Signale folgen,': ['Follow signals', 'Sigue señales', 'Следуй сигналам', 'اتبع الإشارات'],
    'ohne abzutippen.': ['without typing.', 'sin teclear.', 'без ручного ввода.', 'دون كتابة.'],
    'Für alle, die Signalgruppen folgen wollen, aber keine Zeit haben, jedes Signal mitzuschreiben. AURON setzt es in Sekunden um – auch nachts, auch wenn du gerade unterwegs bist.': [
      'For everyone who wants to follow signal groups but has no time to copy every signal. AURON places it in seconds – at night too, even when you are out.',
      'Para quien quiere seguir grupos de señales pero no tiene tiempo de copiar cada una. AURON la ejecuta en segundos – también de noche, aunque estés fuera.',
      'Для тех, кто хочет следовать сигнальным группам, но не успевает переписывать каждый сигнал. AURON исполняет его за секунды – и ночью, и когда ты в дороге.',
      'لكل من يريد متابعة مجموعات الإشارات دون وقت لنسخ كل إشارة. ينفّذها AURON خلال ثوانٍ – ليلاً أيضاً، وحتى وأنت خارج المنزل.'],
    'Kein verpasstes Signal mehr. Keine Tippfehler bei Kurs und Lotgröße.': ['No more missed signals. No typos in price or lot size.', 'Ni una señal perdida. Ni errores en precio o lote.', 'Ни одного пропущенного сигнала. Никаких опечаток в цене и лоте.', 'لا إشارات فائتة بعد اليوم. ولا أخطاء في السعر أو حجم اللوت.'],
    'Sofort auf dem Konto': ['Straight to your account', 'Directo a tu cuenta', 'Сразу на счёте', 'مباشرة إلى حسابك'],
    'Vom Telegram-Signal direkt in MetaTrader 5 – mit deinem Risiko oder fester Lotgröße.': ['From the Telegram signal straight into MetaTrader 5 – with your risk or a fixed lot size.', 'De la señal de Telegram directo a MetaTrader 5 – con tu riesgo o un lote fijo.', 'Из сигнала в Telegram прямо в MetaTrader 5 – с твоим риском или фиксированным лотом.', 'من إشارة تيليغرام مباشرة إلى ميتاتريدر 5 – بالمخاطرة التي تحددها أو بحجم لوت ثابت.'],
    'Gewinne absichern': ['Lock in profits', 'Asegura ganancias', 'Фиксация прибыли', 'تأمين الأرباح'],
    'Teilgewinne, Break-even, Trailing-Stop – je Gruppe einstellbar.': ['Partial profits, break-even, trailing stop – set per group.', 'Cierres parciales, break-even, trailing stop – por grupo.', 'Частичная фиксация, безубыток, трейлинг-стоп – для каждой группы.', 'أرباح جزئية، نقطة التعادل، وقف متحرك – لكل مجموعة.'],
    'Klare Bilanz je Gruppe': ['Clear results per group', 'Resultados claros por grupo', 'Ясный итог по каждой группе', 'نتائج واضحة لكل مجموعة'],
    'Welche Gruppe liefert – und welche nur kostet.': ['Which group delivers – and which only costs.', 'Qué grupo rinde – y cuál solo cuesta.', 'Какая группа приносит – а какая только стоит.', 'أي مجموعة تربح – وأيها تكلّف فقط.'],
    'Notbremse immer griffbereit': ['Emergency brake always at hand', 'Freno de emergencia siempre a mano', 'Стоп-кран всегда под рукой', 'مكابح الطوارئ دائماً في متناولك'],
    'Pausieren oder alles schließen – per Klick oder Stimme.': ['Pause or close everything – by click or voice.', 'Pausa o cierra todo – con un clic o por voz.', 'Пауза или закрыть всё – кликом или голосом.', 'أوقف مؤقتاً أو أغلق كل شيء – بنقرة أو بالصوت.'],
    'Daten statt': ['Data instead of', 'Datos en vez de', 'Данные вместо', 'بيانات بدلاً من'],
    'Bauchgefühl.': ['gut feeling.', 'corazonadas.', 'интуиции.', 'الحدس.'],
    'AURON wertet die offiziellen Insider-Meldungen der SEC aus und prüft über Jahre, wessen Käufe sich tatsächlich gelohnt haben. Aus dieser Profi-Liste baust du deine Beobachtungsliste.': [
      'AURON analyses the official SEC insider filings and checks over years whose purchases actually paid off. From this pro list you build your watchlist.',
      'AURON analiza los informes oficiales de insiders de la SEC y comprueba durante años qué compras realmente rindieron. Con esta lista de profesionales armas tu lista de seguimiento.',
      'AURON анализирует официальные отчёты инсайдеров в SEC и за годы проверяет, чьи покупки действительно окупились. Из этого списка профи ты собираешь свой список наблюдения.',
      'يحلل AURON إفصاحات المطّلعين الرسمية لدى هيئة SEC ويتحقق على مدى سنوات من الذين أثمرت مشترياتهم فعلاً. ومن قائمة المحترفين هذه تبني قائمة المتابعة الخاصة بك.'],
    'Statt Gerüchten und Schätzungen: nachvollziehbare Zahlen, ohne Rückblick-Trick geprüft.': ['Instead of rumours and guesses: traceable numbers, tested without hindsight.', 'En vez de rumores y estimaciones: cifras verificables, probadas sin trampa retrospectiva.', 'Вместо слухов и догадок – проверяемые цифры, без подгонки задним числом.', 'بدلاً من الشائعات والتخمين: أرقام قابلة للتحقق، مختبرة دون أثر رجعي.'],
    'Profi-Liste': ['Pro list', 'Lista de profesionales', 'Список профи', 'قائمة المحترفين'],
    'Insider, deren Käufe sich nachweislich gelohnt haben – mit Trefferquote und Ergebnis.': ['Insiders whose purchases have provably paid off – with hit rate and result.', 'Insiders cuyas compras han rendido de forma comprobada – con tasa de acierto y resultado.', 'Инсайдеры, чьи покупки доказанно окупились – с процентом попаданий и результатом.', 'مطّلعون أثبتت مشترياتهم جدواها – مع نسبة النجاح والنتيجة.'],
    'Deine Beobachtungsliste': ['Your watchlist', 'Tu lista de seguimiento', 'Твой список наблюдения', 'قائمة متابعتك'],
    'Ein Klick auf ☆ setzt einen Profi auf deine Liste – jeder neue Trade von ihm kommt sofort aufs Handy.': ['One tap on ☆ adds a pro to your list – every new trade of theirs reaches your phone at once.', 'Un toque en ☆ añade un profesional a tu lista – cada nueva operación suya llega al móvil al instante.', 'Нажми ☆ – и профи в твоём списке: каждая его новая сделка сразу приходит на телефон.', 'نقرة على ☆ تضيف محترفاً إلى قائمتك – وتصلك كل صفقة جديدة له فوراً على الهاتف.'],
    'Strategie aus Daten': ['Strategy from data', 'Estrategia basada en datos', 'Стратегия на данных', 'استراتيجية من البيانات'],
    'in Entwicklung': ['in development', 'en desarrollo', 'в разработке', 'قيد التطوير'],
    'AURON leitet aus deiner Liste Regeln für Einstieg, Haltedauer und Absicherung ab – auf Basis von Analysen, nicht Schätzungen.': ['AURON derives rules for entry, holding period and hedging from your list – based on analysis, not guesses.', 'AURON deriva de tu lista reglas de entrada, duración y cobertura – con análisis, no estimaciones.', 'AURON выводит из твоего списка правила входа, срока удержания и защиты – на основе анализа, а не догадок.', 'يستخلص AURON من قائمتك قواعد للدخول ومدة الاحتفاظ والتحوط – بناءً على التحليل لا التخمين.'],
    'Makro im Blick': ['Macro in view', 'Macro a la vista', 'Макро под контролем', 'الاقتصاد الكلي تحت نظرك'],
    'Zinsentscheid, Inflation, Arbeitsmarkt – Warnung 30 Minuten vorher.': ['Rate decisions, inflation, jobs data – alert 30 minutes ahead.', 'Tipos de interés, inflación, empleo – aviso 30 minutos antes.', 'Ставки, инфляция, рынок труда – сигнал за 30 минут.', 'قرارات الفائدة والتضخم وسوق العمل – تنبيه قبل 30 دقيقة.'],
    'Ein Kontrolleur': ['One controller', 'Un controlador', 'Один контролёр', 'مراقب واحد'],
    'statt fünf Terminals.': ['instead of five terminals.', 'en vez de cinco terminales.', 'вместо пяти терминалов.', 'بدلاً من خمس منصات.'],
    'AURON ist kein Automat, der auf eigene Faust handelt. Er ist dein Kontrolleur: Er überwacht Konten, Gruppen und Bots rund um die Uhr, wertet aus und beobachtet – und hilft dir so, deine Strategie besser zu machen.': [
      'AURON is not a machine that trades on its own. It is your controller: it watches accounts, groups and bots around the clock, analyses and observes – and so helps you improve your strategy.',
      'AURON no es una máquina que opera por su cuenta. Es tu controlador: vigila cuentas, grupos y bots día y noche, analiza y observa – y así te ayuda a mejorar tu estrategia.',
      'AURON – не автомат, торгующий сам по себе. Это твой контролёр: он круглосуточно следит за счетами, группами и ботами, анализирует и наблюдает – и помогает улучшить стратегию.',
      'AURON ليس آلة تتداول من تلقاء نفسها. إنه مراقبك: يراقب الحسابات والمجموعات والروبوتات على مدار الساعة، ويحلل ويتابع – ويساعدك بذلك على تحسين استراتيجيتك.'],
    'Statt fünf Terminals durchzuklicken: eine Karte, die alles zeigt – und sich meldet, wenn etwas nicht stimmt.': ['Instead of clicking through five terminals: one card that shows everything – and speaks up when something is wrong.', 'En vez de revisar cinco terminales: una tarjeta que lo muestra todo – y avisa cuando algo falla.', 'Вместо пяти терминалов – одна карточка, которая показывает всё и сообщает, если что-то не так.', 'بدلاً من التنقل بين خمس منصات: بطاقة واحدة تعرض كل شيء – وتنبّهك عند حدوث خلل.'],
    'Alle Konten auf einen Blick': ['All accounts at a glance', 'Todas las cuentas de un vistazo', 'Все счета на одном экране', 'كل الحسابات بنظرة واحدة'],
    'Kontostand, offene Positionen und Ergebnis jedes Kontos – ohne ein Terminal zu öffnen.': ['Balance, open positions and result of every account – without opening a terminal.', 'Saldo, posiciones abiertas y resultado de cada cuenta – sin abrir un terminal.', 'Баланс, открытые позиции и результат каждого счёта – без открытия терминала.', 'الرصيد والصفقات المفتوحة ونتيجة كل حساب – دون فتح أي منصة.'],
    'Gruppen, Bots und KIs überwacht': ['Groups, bots and AIs monitored', 'Grupos, bots e IAs vigilados', 'Группы, боты и ИИ под наблюдением', 'مراقبة المجموعات والروبوتات والذكاء الاصطناعي'],
    'Läuft, pausiert, offline: Fällt etwas aus, kommt die Meldung aufs Handy.': ['Running, paused, offline: if something fails, your phone hears about it.', 'Activo, en pausa, desconectado: si algo falla, te llega al móvil.', 'Работает, на паузе, офлайн: если что-то упало – сообщение на телефон.', 'يعمل، متوقف، غير متصل: إذا تعطل شيء يصلك إشعار على الهاتف.'],
    'Analyse statt Bauchgefühl': ['Analysis instead of gut feeling', 'Análisis en vez de corazonadas', 'Анализ вместо интуиции', 'تحليل بدلاً من الحدس'],
    'Welche Gruppe, welcher Bot, welche Uhrzeit bringt wirklich etwas – ausgewertet aus deinen echten Trades.': ['Which group, which bot, which time of day really pays – analysed from your real trades.', 'Qué grupo, qué bot, qué hora rinde de verdad – analizado con tus operaciones reales.', 'Какая группа, какой бот, какое время реально приносят – по твоим настоящим сделкам.', 'أي مجموعة وأي روبوت وأي توقيت يحقق نتائج فعلاً – من تحليل صفقاتك الحقيقية.'],
    'Strategie mit Claude Code bauen': ['Build strategies with Claude Code', 'Crea estrategias con Claude Code', 'Стратегии с Claude Code', 'ابنِ استراتيجيات مع Claude Code'],
    'Aus Beobachtung wird ein Plan: Mit Claude Code entsteht deine Strategie, auf Wunsch bis zum fertigen MT5-Bot – live nur mit deiner Freigabe.': ['Observation becomes a plan: with Claude Code your strategy takes shape, up to a finished MT5 bot if you like – live only with your approval.', 'La observación se vuelve plan: con Claude Code nace tu estrategia, hasta un bot MT5 terminado si quieres – en vivo solo con tu aprobación.', 'Наблюдение превращается в план: с Claude Code рождается стратегия, при желании – до готового бота MT5. В бой – только с твоего одобрения.', 'تتحول الملاحظة إلى خطة: مع Claude Code تتشكل استراتيجيتك، وحتى روبوت MT5 جاهز إن أردت – ولا يعمل فعلياً إلا بموافقتك.'],
    'Vergangene Ergebnisse garantieren keine künftigen. AURON liefert Daten und Werkzeuge, keine Anlageberatung.': ['Past results do not guarantee future ones. AURON provides data and tools, not investment advice.', 'Los resultados pasados no garantizan los futuros. AURON ofrece datos y herramientas, no asesoramiento de inversión.', 'Прошлые результаты не гарантируют будущих. AURON даёт данные и инструменты, а не инвестиционные советы.', 'النتائج السابقة لا تضمن النتائج المستقبلية. يقدم AURON بيانات وأدوات، وليس نصائح استثمارية.'],
    'Baukasten': ['Building blocks', 'A tu medida', 'Конструктор', 'بنظام الوحدات'],
    'Ein Dashboard. Deine Manager.': ['One dashboard. Your managers.', 'Un panel. Tus gestores.', 'Один дашборд. Твои модули.', 'لوحة واحدة. مديروك.'],
    'Nimm, was zu deinem Alltag passt – für Trader, Signalgruppen, Creator, Shops und alle, die im Homeoffice viel im Blick behalten müssen. Jeder Manager ist eine Karte auf deinem Dashboard.': [
      'Take what fits your day – for traders, signal groups, creators, shops and everyone working from home with a lot to keep an eye on. Each manager is a card on your dashboard.',
      'Elige lo que encaja con tu día – para traders, grupos de señales, creadores, tiendas y quien trabaja desde casa con mucho que vigilar. Cada gestor es una tarjeta en tu panel.',
      'Бери то, что подходит твоему дню, – для трейдеров, сигнальных групп, креаторов, магазинов и всех, кто работает из дома и многое держит в голове. Каждый модуль – карточка на дашборде.',
      'اختر ما يناسب يومك – للمتداولين ومجموعات الإشارات وصنّاع المحتوى والمتاجر وكل من يعمل من المنزل ويتابع الكثير. كل مدير بطاقة على لوحتك.'],
    'Signal-Manager': ['Signal Manager', 'Gestor de señales', 'Сигналы', 'مدير الإشارات'],
    'Telegram-Signale automatisch auf deine MT5-Konten, mit Break-even und Trailing.': ['Telegram signals to your MT5 accounts automatically, with break-even and trailing.', 'Señales de Telegram a tus cuentas MT5 automáticamente, con break-even y trailing.', 'Сигналы Telegram автоматически на твои счета MT5, с безубытком и трейлингом.', 'إشارات تيليغرام إلى حسابات MT5 تلقائياً، مع التعادل والوقف المتحرك.'],
    'Signalgruppen · Follower': ['Signal groups · Followers', 'Grupos de señales · Seguidores', 'Сигнальные группы · Подписчики', 'مجموعات الإشارات · المتابعون'],
    'Trading-Manager': ['Trading Manager', 'Gestor de trading', 'Трейдинг', 'مدير التداول'],
    'Alle Konten, Bots und Ergebnisse auf einen Blick, Ausfall-Alarm aufs Handy.': ['All accounts, bots and results at a glance, outage alerts to your phone.', 'Todas las cuentas, bots y resultados de un vistazo, alertas de caída al móvil.', 'Все счета, боты и результаты на одном экране, тревога о сбоях на телефон.', 'كل الحسابات والروبوتات والنتائج بنظرة واحدة، وتنبيهات الأعطال على الهاتف.'],
    'Trader · Algo-Bots': ['Traders · Algo bots', 'Traders · Bots algorítmicos', 'Трейдеры · Алго-боты', 'المتداولون · الروبوتات الآلية'],
    'Instagram-Manager': ['Instagram Manager', 'Gestor de Instagram', 'Instagram', 'مدير إنستغرام'],
    'Fotos aus deinem Drive bearbeitet, bewertet, geschnitten, mit Caption geplant.': ['Photos from your Drive edited, rated, cut and scheduled with a caption.', 'Fotos de tu Drive editadas, valoradas, cortadas y programadas con caption.', 'Фото из Drive обработаны, оценены, смонтированы и запланированы с подписью.', 'صور من Drive معدّلة ومقيّمة ومقصوصة ومجدولة مع تعليق.'],
    'Creator · Influencer': ['Creators · Influencers', 'Creadores · Influencers', 'Креаторы · Блогеры', 'صنّاع المحتوى · المؤثرون'],
    'Mail-Manager': ['Mail Manager', 'Gestor de correo', 'Почта', 'مدير البريد'],
    'Wichtiges zuerst, Werbung raus, Antworten als Entwurf zum Freigeben.': ['Important first, promos out, replies drafted for you to approve.', 'Lo importante primero, publicidad fuera, respuestas en borrador para aprobar.', 'Важное – вперёд, реклама – прочь, ответы – черновиком на одобрение.', 'المهم أولاً، والإعلانات خارجاً، والردود مسودات بانتظار موافقتك.'],
    'Selbstständige · Homeoffice': ['Freelancers · Home office', 'Autónomos · Teletrabajo', 'Фрилансеры · Удалёнка', 'المستقلون · العمل من المنزل'],
    'Markt-Manager': ['Market Manager', 'Gestor de mercado', 'Рынки', 'مدير السوق'],
    'Watchlist, Makro-Termine und Insider-Trades mit Warnung vorab.': ['Watchlist, macro dates and insider trades with alerts in advance.', 'Watchlist, fechas macro y operaciones de insiders con aviso previo.', 'Watchlist, макро-события и сделки инсайдеров с заблаговременным сигналом.', 'قائمة المتابعة والمواعيد الاقتصادية وصفقات المطّلعين مع تنبيه مسبق.'],
    'Trader · Investoren': ['Traders · Investors', 'Traders · Inversores', 'Трейдеры · Инвесторы', 'المتداولون · المستثمرون'],
    'E-Commerce-Manager': ['E-commerce Manager', 'Gestor de e-commerce', 'E-commerce', 'مدير التجارة الإلكترونية'],
    'bald': ['soon', 'pronto', 'скоро', 'قريباً'],
    'Bestellungen, Kundenanfragen und Social Media deines Shops in einer Karte.': ['Orders, customer questions and social media of your shop in one card.', 'Pedidos, consultas de clientes y redes de tu tienda en una tarjeta.', 'Заказы, вопросы клиентов и соцсети магазина в одной карточке.', 'الطلبات واستفسارات العملاء ووسائل التواصل لمتجرك في بطاقة واحدة.'],
    'Shops · Marken': ['Shops · Brands', 'Tiendas · Marcas', 'Магазины · Бренды', 'المتاجر · العلامات التجارية'],
    'Das AURON-Dashboard: Trading, Watchlist, Instagram, Post und Smart Money um einen Hologramm-Planeten': ['The AURON dashboard: trading, watchlist, Instagram, mail and smart money around a hologram planet', 'El panel de AURON: trading, watchlist, Instagram, correo y smart money alrededor de un planeta holográfico', 'Дашборд AURON: трейдинг, watchlist, Instagram, почта и smart money вокруг голографической планеты', 'لوحة AURON: التداول وقائمة المتابعة وإنستغرام والبريد والأموال الذكية حول كوكب هولوغرامي'],
    '⤢ Zum Vergrößern klicken': ['⤢ Tap to enlarge', '⤢ Toca para ampliar', '⤢ Нажми, чтобы увеличить', '⤢ انقر للتكبير'],
    'Ein Überblick statt ständigem Wechseln.': ['One overview instead of constant switching.', 'Una vista en lugar de saltar sin parar.', 'Один обзор вместо постоянных переключений.', 'نظرة شاملة بدلاً من التنقل المستمر.'],
    'Konten, Bots, Post und Content an einem Ort – weniger zwischen Tools wechseln.': ['Accounts, bots, mail and content in one place – less switching between tools.', 'Cuentas, bots, correo y contenido en un lugar – menos saltos entre herramientas.', 'Счета, боты, почта и контент в одном месте – меньше переключений.', 'الحسابات والروبوتات والبريد والمحتوى في مكان واحد – تنقل أقل بين الأدوات.'],
    'Vom Überblick direkt zur Aktion: Jede Karte öffnet Details und Verlauf.': ['From overview straight to action: every card opens details and history.', 'De la vista a la acción: cada tarjeta abre detalles e historial.', 'От обзора сразу к действию: каждая карточка открывает детали и историю.', 'من النظرة العامة إلى الإجراء مباشرة: كل بطاقة تفتح التفاصيل والسجل.'],
    'Das Wichtigste zuerst: Ordne Karten und Bereiche nach deinen Prioritäten.': ['What matters first: arrange cards and areas by your priorities.', 'Lo importante primero: ordena tarjetas y áreas según tus prioridades.', 'Главное – вперёд: расставь карточки по своим приоритетам.', 'الأهم أولاً: رتّب البطاقات والأقسام حسب أولوياتك.'],
    'Dein Design': ['Your design', 'Tu diseño', 'Твой дизайн', 'تصميمك'],
    'Ein Arbeitsplatz, der sich nach dir anfühlt.': ['A workspace that feels like you.', 'Un espacio de trabajo que se siente tuyo.', 'Рабочее место, которое ощущается твоим.', 'مساحة عمل تشبهك.'],
    'Dein Stil, dein Überblick: Passe Räume, Kartenfarbe, Glasart, Planet und Uhr an. Entdecke oben mit ‹ › deinen Favoriten.': ['Your style, your overview: adjust rooms, card colour, glass, planet and clock. Find your favourite above with ‹ ›.', 'Tu estilo, tu vista: ajusta salas, color de tarjetas, vidrio, planeta y reloj. Encuentra tu favorito arriba con ‹ ›.', 'Твой стиль, твой обзор: меняй комнаты, цвет карточек, стекло, планету и часы. Выбери любимый вариант наверху стрелками ‹ ›.', 'أسلوبك ونظرتك: عدّل الغرف ولون البطاقات والزجاج والكوكب والساعة. اكتشف المفضل لديك في الأعلى عبر ‹ ›.'],
    'Wald mit Wasserfall': ['Forest with waterfall', 'Bosque con cascada', 'Лес с водопадом', 'غابة مع شلال'],
    'Alpen bei Sonnenuntergang': ['Alps at sunset', 'Alpes al atardecer', 'Альпы на закате', 'جبال الألب عند الغروب'],
    'Über der Erde': ['Above the Earth', 'Sobre la Tierra', 'Над Землёй', 'فوق الأرض'],
    'Bald verfügbar': ['Coming soon', 'Próximamente', 'Скоро', 'قريباً'],
    'AURON im Raum.': ['AURON in the room.', 'AURON en tu espacio.', 'AURON в комнате.', 'AURON في الغرفة.'],
    'Als Hologramm.': ['As a hologram.', 'Como holograma.', 'В виде голограммы.', 'كصورة هولوغرامية.'],
    'Ein Hologramm-Ventilator auf dem Schreibtisch oder im Regal – und AURON schwebt frei in der Luft, live: der Planet mit seinen Ringen, die leuchten, wenn deine Gruppen im Plus sind. Oder gleich das ganze Dashboard, mit Konten, Post und Terminen.': [
      'A hologram fan on your desk or shelf – and AURON floats in mid-air, live: the planet with its rings that glow when your groups are in profit. Or the whole dashboard, with accounts, mail and dates.',
      'Un ventilador holográfico en el escritorio o la estantería – y AURON flota en el aire, en vivo: el planeta con sus anillos que brillan cuando tus grupos están en positivo. O el panel completo, con cuentas, correo y citas.',
      'Голографический вентилятор на столе или полке – и AURON парит в воздухе вживую: планета с кольцами, которые светятся, когда твои группы в плюсе. Или весь дашборд со счетами, почтой и событиями.',
      'مروحة هولوغرام على مكتبك أو رفّك – ويطفو AURON في الهواء مباشرة: الكوكب بحلقاته التي تضيء حين تكون مجموعاتك في الربح. أو اللوحة كاملة بالحسابات والبريد والمواعيد.'],
    'Nur der Planet oder das ganze Dashboard – du entscheidest und wechselst jederzeit.': ['Just the planet or the whole dashboard – you decide and switch any time.', 'Solo el planeta o el panel completo – tú decides y cambias cuando quieras.', 'Только планета или весь дашборд – решаешь ты и меняешь когда угодно.', 'الكوكب وحده أو اللوحة كاملة – أنت تقرر وتغيّر متى شئت.'],
    'AURON als Hologramm: über einem Ventilator auf dem Schreibtisch schwebt das Dashboard – Planet in der Mitte, Karten links und rechts': ['AURON as a hologram: the dashboard floats above a fan on the desk – planet in the middle, cards left and right', 'AURON como holograma: el panel flota sobre un ventilador en el escritorio – planeta al centro, tarjetas a los lados', 'AURON голограммой: дашборд парит над вентилятором на столе – планета в центре, карточки по бокам', 'AURON كهولوغرام: تطفو اللوحة فوق مروحة على المكتب – الكوكب في الوسط والبطاقات على الجانبين'],
    'Bild folgt': ['Image coming', 'Imagen próximamente', 'Изображение скоро', 'الصورة قريباً'],
    'Routine abgeben. Kontrolle behalten.': ['Hand over routine. Keep control.', 'Delega la rutina. Mantén el control.', 'Отдай рутину. Сохрани контроль.', 'سلّم الروتين. واحتفظ بالتحكم.'],
    'Du bestimmst, was AURON automatisiert und wo er deine Freigabe braucht. Mails und Posts prüfst du vor dem Versand. Der Signal-Kopierer arbeitet innerhalb deiner festgelegten Trading-Regeln.': ['You decide what AURON automates and where it needs your approval. You check emails and posts before they go out. The signal copier works within the trading rules you set.', 'Tú decides qué automatiza AURON y dónde necesita tu aprobación. Revisas correos y posts antes de enviarlos. El copiador de señales opera dentro de tus reglas de trading.', 'Ты решаешь, что AURON автоматизирует и где нужно твоё одобрение. Письма и посты проверяешь перед отправкой. Копировщик сигналов работает в рамках твоих торговых правил.', 'أنت تحدد ما يؤتمته AURON وأين يحتاج موافقتك. تراجع الرسائل والمنشورات قبل إرسالها. ويعمل ناسخ الإشارات ضمن قواعد التداول التي تضعها.'],
    'Du gibst den Rahmen vor': ['You set the frame', 'Tú pones el marco', 'Рамки задаёшь ты', 'أنت تضع الإطار'],
    'Mails und Posts nach Freigabe. Trading nach deinen Regeln.': ['Emails and posts after approval. Trading by your rules.', 'Correos y posts tras tu aprobación. Trading según tus reglas.', 'Письма и посты – после одобрения. Торговля – по твоим правилам.', 'الرسائل والمنشورات بعد الموافقة. والتداول وفق قواعدك.'],
    'Lokal auf deinem Rechner': ['Local on your machine', 'En local, en tu equipo', 'Локально на твоём компьютере', 'محلياً على جهازك'],
    'Deine AURON-Zentrale läuft bei dir – mit deinen eigenen Kontozugängen.': ['Your AURON hub runs on your side – with your own account logins.', 'Tu central AURON funciona contigo – con tus propios accesos.', 'Твой центр AURON работает у тебя – с твоими собственными доступами.', 'مركز AURON يعمل لديك – بحساباتك الخاصة.'],
    'Alles nachvollziehbar': ['Everything traceable', 'Todo trazable', 'Всё прозрачно', 'كل شيء قابل للتتبع'],
    'Sieh im Protokoll, was AURON wann erledigt hat – ohne rätseln zu müssen.': ['See in the log what AURON did and when – no guessing.', 'Mira en el registro qué hizo AURON y cuándo – sin adivinar.', 'В журнале видно, что и когда сделал AURON, – без догадок.', 'اطّلع في السجل على ما أنجزه AURON ومتى – دون تخمين.'],
    'Verschlüsselte Sicherung': ['Encrypted backup', 'Copia de seguridad cifrada', 'Зашифрованный бэкап', 'نسخ احتياطي مشفّر'],
    'Nächtliche Backups an drei Orten erleichtern die Wiederherstellung.': ['Nightly backups in three places make restoring easy.', 'Copias nocturnas en tres lugares facilitan la restauración.', 'Ночные бэкапы в трёх местах упрощают восстановление.', 'نسخ احتياطية ليلية في ثلاثة أماكن تسهّل الاستعادة.'],
    "So funktioniert's": ['How it works', 'Cómo funciona', 'Как это работает', 'كيف يعمل'],
    'Einmal einrichten. Im Alltag entlastet.': ['Set up once. Relieved every day.', 'Configura una vez. Alivio cada día.', 'Настроил один раз – свободнее каждый день.', 'إعداد مرة واحدة. وراحة كل يوم.'],
    'Verbinden': ['Connect', 'Conecta', 'Подключи', 'اربط'],
    'Verbinde die Konten und Kanäle, die du nutzen möchtest – mit deiner eigenen Anmeldung.': ['Connect the accounts and channels you want to use – with your own login.', 'Conecta las cuentas y canales que quieras usar – con tu propio inicio de sesión.', 'Подключи нужные счета и каналы – со своим входом.', 'اربط الحسابات والقنوات التي تريد استخدامها – بتسجيل دخولك الخاص.'],
    'Regeln setzen': ['Set rules', 'Define reglas', 'Задай правила', 'ضع القواعد'],
    'Lege Gruppen, Risikolimits, Alarme und Freigaben fest. AURON richtet sich nach deinen Vorgaben.': ['Set groups, risk limits, alerts and approvals. AURON follows your rules.', 'Define grupos, límites de riesgo, alertas y aprobaciones. AURON sigue tus indicaciones.', 'Задай группы, лимиты риска, оповещения и одобрения. AURON следует твоим правилам.', 'حدّد المجموعات وحدود المخاطرة والتنبيهات والموافقات. ويلتزم AURON بتوجيهاتك.'],
    'Zeit zurückgewinnen': ['Win back time', 'Recupera tiempo', 'Верни время', 'استعد وقتك'],
    'Lass AURON die Routine übernehmen. Du prüfst Ergebnisse und Freigaben, statt jeden Schritt selbst zu erledigen.': ['Let AURON take over the routine. You check results and approvals instead of doing every step yourself.', 'Deja la rutina a AURON. Tú revisas resultados y aprobaciones en lugar de hacer cada paso.', 'Пусть рутину возьмёт AURON. Ты проверяешь результаты и одобрения, а не делаешь всё сам.', 'دع AURON يتولى الروتين. تراجع النتائج والموافقات بدلاً من تنفيذ كل خطوة بنفسك.'],
    'Fair von Anfang an. 30 Tage kostenlos testen.': ['Fair from day one. Try it free for 30 days.', 'Justo desde el inicio. Pruébalo gratis 30 días.', 'Честно с первого дня. 30 дней бесплатно.', 'عادل منذ البداية. جرّبه مجاناً 30 يوماً.'],
    'Alle Pakete monatlich kündbar. Jährlich gezahlt: zwei Monate geschenkt. AURON wird derzeit privat getestet – Preise vorläufig, noch nicht buchbar.': ['All plans cancel monthly. Paid yearly: two months free. AURON is in private testing – prices are provisional and not yet bookable.', 'Todos los planes se cancelan mensualmente. Pago anual: dos meses gratis. AURON está en prueba privada – precios provisionales, aún no disponibles.', 'Все тарифы можно отменить помесячно. При оплате за год – два месяца в подарок. AURON сейчас на закрытом тесте – цены предварительные, оформить пока нельзя.', 'جميع الباقات قابلة للإلغاء شهرياً. عند الدفع السنوي: شهران مجاناً. AURON قيد الاختبار الخاص حالياً – الأسعار مبدئية وغير متاحة للحجز بعد.'],
    'Insta-Manager': ['Insta Manager', 'Insta Manager', 'Insta Manager', 'مدير إنستا'],
    '/Monat': ['/month', '/mes', '/мес.', '/شهرياً'],
    'Für Creator und Shops – ganz ohne Trading.': ['For creators and shops – no trading at all.', 'Para creadores y tiendas – sin trading.', 'Для креаторов и магазинов – без трейдинга.', 'لصنّاع المحتوى والمتاجر – دون أي تداول.'],
    '1 Instagram-Konto': ['1 Instagram account', '1 cuenta de Instagram', '1 аккаунт Instagram', 'حساب إنستغرام واحد'],
    'Fotos & Videos aus deinem Drive': ['Photos & videos from your Drive', 'Fotos y vídeos de tu Drive', 'Фото и видео из твоего Drive', 'صور وفيديوهات من Drive'],
    'Bearbeitung nach deinem Preset': ['Editing with your preset', 'Edición con tu preset', 'Обработка по твоему пресету', 'تعديل بإعداداتك'],
    'Bewertung, Auswahl, Videoschnitt': ['Rating, selection, video cutting', 'Valoración, selección, edición de vídeo', 'Оценка, отбор, монтаж видео', 'تقييم واختيار وقص الفيديو'],
    'Kennzeichen automatisch unkenntlich': ['Licence plates blurred automatically', 'Matrículas difuminadas automáticamente', 'Номера машин скрываются автоматически', 'إخفاء لوحات السيارات تلقائياً'],
    'Captions in deiner Stimme, Postplanung': ['Captions in your voice, post scheduling', 'Captions con tu voz, programación', 'Подписи твоим голосом, планирование', 'تعليقات بصوتك وجدولة المنشورات'],
    'Postfach sortiert, Notizen': ['Sorted inbox, notes', 'Correo ordenado, notas', 'Почта по порядку, заметки', 'بريد مرتب وملاحظات'],
    'Für alle, die Signalgruppen folgen.': ['For everyone following signal groups.', 'Para quien sigue grupos de señales.', 'Для всех, кто следует сигнальным группам.', 'لكل من يتابع مجموعات الإشارات.'],
    '3 Kopierer-Konten (MT5)': ['3 copier accounts (MT5)', '3 cuentas de copiado (MT5)', '3 счёта копировщика (MT5)', '3 حسابات نسخ (MT5)'],
    'Telegram-Gruppen ohne Limit': ['Unlimited Telegram groups', 'Grupos de Telegram ilimitados', 'Группы Telegram без лимита', 'مجموعات تيليغرام بلا حدود'],
    'Risiko % oder feste Lotgröße': ['Risk % or fixed lot size', 'Riesgo % o lote fijo', 'Риск % или фиксированный лот', 'نسبة مخاطرة أو لوت ثابت'],
    'Teilgewinne, Break-even, Trailing-Stop': ['Partial profits, break-even, trailing stop', 'Cierres parciales, break-even, trailing stop', 'Частичная фиксация, безубыток, трейлинг-стоп', 'أرباح جزئية، تعادل، وقف متحرك'],
    'Bilanz je Gruppe': ['Results per group', 'Resultados por grupo', 'Итог по группам', 'نتائج لكل مجموعة'],
    'Dashboard, Handy-Alarme, Notbremse': ['Dashboard, phone alerts, emergency brake', 'Panel, alertas al móvil, freno de emergencia', 'Дашборд, оповещения на телефон, стоп-кран', 'لوحة تحكم، تنبيهات الهاتف، مكابح الطوارئ'],
    'Postfach sortiert': ['Sorted inbox', 'Correo ordenado', 'Почта по порядку', 'بريد مرتب'],
    'Beliebt': ['Popular', 'Popular', 'Популярный', 'الأكثر طلباً'],
    'Für Trader mit mehreren Konten und Bots.': ['For traders with several accounts and bots.', 'Para traders con varias cuentas y bots.', 'Для трейдеров с несколькими счетами и ботами.', 'للمتداولين بعدة حسابات وروبوتات.'],
    'Alles aus Signal, 10 Konten': ['Everything in Signal, 10 accounts', 'Todo lo de Signal, 10 cuentas', 'Всё из Signal, 10 счетов', 'كل ما في Signal، و10 حسابات'],
    'Bot- & Konto-Überwachung, Ausfall-Alarm': ['Bot & account monitoring, outage alerts', 'Vigilancia de bots y cuentas, alertas de caída', 'Мониторинг ботов и счетов, тревога о сбоях', 'مراقبة الروبوتات والحسابات، تنبيهات الأعطال'],
    'Smart Money: Insider, Profi-Liste': ['Smart money: insiders, pro list', 'Smart money: insiders, lista de profesionales', 'Smart money: инсайдеры, список профи', 'الأموال الذكية: المطّلعون وقائمة المحترفين'],
    'Makro-Kalender mit Warnung': ['Macro calendar with alerts', 'Calendario macro con avisos', 'Макро-календарь с оповещениями', 'تقويم اقتصادي مع تنبيهات'],
    'Assistent mit Stimme': ['Voice assistant', 'Asistente con voz', 'Голосовой ассистент', 'مساعد صوتي'],
    'Karten frei gestalten': ['Customise your cards', 'Personaliza las tarjetas', 'Свободная настройка карточек', 'تخصيص البطاقات بحرية'],
    'Volle Leistung – für Büros und Vielbeschäftigte.': ['Full power – for offices and busy people.', 'Máxima potencia – para oficinas y gente ocupada.', 'Полная мощность – для офисов и занятых людей.', 'قوة كاملة – للمكاتب وكثيري الانشغال.'],
    'Alles aus Trader, Konten unbegrenzt': ['Everything in Trader, unlimited accounts', 'Todo lo de Trader, cuentas ilimitadas', 'Всё из Trader, счета без лимита', 'كل ما في Trader، وحسابات غير محدودة'],
    'Insta-Manager inklusive': ['Insta Manager included', 'Insta Manager incluido', 'Insta Manager включён', 'مدير إنستا مشمول'],
    'Alle Module und Räume': ['All modules and rooms', 'Todos los módulos y salas', 'Все модули и комнаты', 'كل الوحدات والغرف'],
    'Strategie & Bot-Bau mit Claude Code': ['Strategy & bot building with Claude Code', 'Estrategia y bots con Claude Code', 'Стратегии и боты с Claude Code', 'بناء الاستراتيجيات والروبوتات مع Claude Code'],
    'Bevorzugter Support': ['Priority support', 'Soporte prioritario', 'Приоритетная поддержка', 'دعم ذو أولوية'],
    'Add-on: Insta-Manager': ['Add-on: Insta Manager', 'Complemento: Insta Manager', 'Дополнение: Insta Manager', 'إضافة: مدير إنستا'],
    'Zu Signal oder Trader dazubuchen:': ['Add it to Signal or Trader:', 'Añádelo a Signal o Trader:', 'Добавь к Signal или Trader:', 'أضفه إلى Signal أو Trader:'],
    '+19 €/Monat': ['+€19/month', '+19 €/mes', '+19 €/мес.', '+19 € شهرياً'],
    '. Jedes weitere Instagram-Konto': ['. Each additional Instagram account', '. Cada cuenta de Instagram adicional', '. Каждый следующий аккаунт Instagram', '. كل حساب إنستغرام إضافي'],
    '+10 €/Monat': ['+€10/month', '+10 €/mes', '+10 €/мес.', '+10 € شهرياً'],
    'Founder Edition · 690 € einmalig': ['Founder Edition · €690 one-time', 'Founder Edition · 690 € pago único', 'Founder Edition · 690 € единоразово', 'إصدار المؤسسين · 690 € مرة واحدة'],
    'Alles aus Business, lebenslang, inklusive Updates. Nur für die ersten 100 Kunden – danach gibt es sie nicht mehr.': ['Everything in Business, for life, updates included. Only for the first 100 customers – then it is gone.', 'Todo lo de Business, de por vida, con actualizaciones. Solo para los primeros 100 clientes – después ya no existe.', 'Всё из Business навсегда, с обновлениями. Только для первых 100 клиентов – потом её не будет.', 'كل ما في Business مدى الحياة مع التحديثات. لأول 100 عميل فقط – ثم لن يكون متاحاً.'],
    'Einrichtung durch uns': ['Set-up by us', 'Instalación por nosotros', 'Настройка под ключ', 'الإعداد من قِبلنا'],
    'Du willst es nicht selbst anschließen? Wir richten AURON für dich ein – Preis nach Aufwand. Beschreib deine Wünsche, AURON schätzt den Aufwand und wir melden uns.': ['Rather not connect it yourself? We set up AURON for you – priced by effort. Describe what you need, AURON estimates the effort and we get back to you.', '¿Prefieres no conectarlo tú? Configuramos AURON por ti – precio según el trabajo. Describe lo que necesitas, AURON estima el esfuerzo y te contactamos.', 'Не хочешь подключать сам? Мы настроим AURON за тебя – цена по объёму работы. Опиши пожелания, AURON оценит объём, и мы свяжемся с тобой.', 'لا تريد ربطه بنفسك؟ نُعدّ AURON لك – والسعر حسب الجهد. صف ما تحتاجه، وسيقدّر AURON الجهد ثم نتواصل معك.'],
    'Chat folgt': ['chat coming', 'chat próximamente', 'чат скоро', 'الدردشة قريباً'],
    'Was du brauchst.': ['What you need.', 'Lo que necesitas.', 'Что тебе нужно.', 'ما تحتاجه.'],
    'AURON läuft bei dir – auf deinem Rechner oder einem eigenen Server. Die Einrichtung führt dich Schritt für Schritt.': ['AURON runs on your side – on your computer or your own server. Setup guides you step by step.', 'AURON funciona contigo – en tu ordenador o tu propio servidor. La instalación te guía paso a paso.', 'AURON работает у тебя – на компьютере или собственном сервере. Установка ведёт тебя шаг за шагом.', 'يعمل AURON لديك – على حاسوبك أو خادمك الخاص. ويرشدك الإعداد خطوة بخطوة.'],
    'Rechner oder VPS': ['Computer or VPS', 'Ordenador o VPS', 'Компьютер или VPS', 'حاسوب أو خادم VPS'],
    'Windows 10/11 oder ein Windows-VPS.': ['Windows 10/11 or a Windows VPS.', 'Windows 10/11 o un VPS con Windows.', 'Windows 10/11 или Windows-VPS.', 'ويندوز 10/11 أو خادم VPS بنظام ويندوز.'],
    'VPS empfohlen': ['VPS recommended', 'VPS recomendado', 'Рекомендуем VPS', 'يُنصح بخادم VPS'],
    '– AURON und der Kopierer laufen dann rund um die Uhr, auch wenn dein PC aus ist.': ['– AURON and the copier then run around the clock, even when your PC is off.', '– AURON y el copiador funcionan día y noche, aunque tu PC esté apagado.', '– тогда AURON и копировщик работают круглосуточно, даже если ПК выключен.', '– فيعمل AURON والناسخ على مدار الساعة حتى لو كان حاسوبك مطفأً.'],
    'Arbeitsspeicher & CPU': ['Memory & CPU', 'Memoria y CPU', 'Память и CPU', 'الذاكرة والمعالج'],
    'Mindestens': ['At least', 'Mínimo', 'Минимум', 'على الأقل'],
    'und 4 Kerne, empfohlen 16 GB. Der Insta-Manager mit Videos braucht am meisten.': ['and 4 cores, 16 GB recommended. The Insta Manager with videos needs the most.', 'y 4 núcleos, recomendados 16 GB. El Insta Manager con vídeos es el que más consume.', 'и 4 ядра, рекомендуется 16 GB. Больше всего нужно Insta Manager с видео.', 'و4 أنوية، ويُنصح بـ16 غيغابايت. مدير إنستا مع الفيديو يحتاج أكثر.'],
    'Speicher': ['Storage', 'Almacenamiento', 'Диск', 'التخزين'],
    '20 GB frei für AURON, dazu Platz für deine Fotos und Videos (Originale bleiben in deinem Google Drive).': ['20 GB free for AURON, plus room for your photos and videos (originals stay in your Google Drive).', '20 GB libres para AURON, más espacio para tus fotos y vídeos (los originales siguen en tu Google Drive).', '20 GB для AURON и место под фото и видео (оригиналы остаются в Google Drive).', '20 غيغابايت لـAURON، ومساحة لصورك وفيديوهاتك (تبقى الأصول في Google Drive).'],
    'Docker Desktop (kostenlos). Für den Kopierer: MetaTrader 5 deines Brokers. Alles Weitere bringt AURON mit.': ['Docker Desktop (free). For the copier: your broker’s MetaTrader 5. AURON brings everything else.', 'Docker Desktop (gratis). Para el copiador: MetaTrader 5 de tu bróker. AURON trae todo lo demás.', 'Docker Desktop (бесплатно). Для копировщика – MetaTrader 5 твоего брокера. Всё остальное AURON принесёт с собой.', 'Docker Desktop (مجاني). وللناسخ: ميتاتريدر 5 من وسيطك. وكل ما عدا ذلك يأتي مع AURON.'],
    'Konten': ['Accounts', 'Cuentas', 'Аккаунты', 'الحسابات'],
    'Je nach Paket: Telegram, Broker-Konto (MT5), Gmail, Google Drive, Instagram-Business-Konto – immer mit deiner eigenen Anmeldung.': ['Depending on the plan: Telegram, broker account (MT5), Gmail, Google Drive, Instagram business account – always with your own login.', 'Según el plan: Telegram, cuenta de bróker (MT5), Gmail, Google Drive, cuenta business de Instagram – siempre con tu propio acceso.', 'В зависимости от тарифа: Telegram, брокерский счёт (MT5), Gmail, Google Drive, бизнес-аккаунт Instagram – всегда со своим входом.', 'حسب الباقة: تيليغرام، حساب وساطة (MT5)، جيميل، Google Drive، حساب إنستغرام للأعمال – دائماً بتسجيل دخولك.'],
    'Stabile Verbindung. Für Signale zählt jede Sekunde – auch deshalb der VPS.': ['A stable connection. For signals every second counts – another reason for the VPS.', 'Conexión estable. En señales cuenta cada segundo – otra razón para el VPS.', 'Стабильное подключение. Для сигналов важна каждая секунда – ещё одна причина взять VPS.', 'اتصال مستقر. مع الإشارات كل ثانية مهمة – وهذا سبب آخر لخادم VPS.'],
    'Unternehmen': ['Company', 'Empresa', 'Компания', 'الشركة'],
    'Wir entwickeln Software, die dir wiederkehrende digitale Arbeit abnimmt. Für Selbstständige, Trader und Unternehmen, die ihre Zeit für mehr als Routine nutzen wollen. AURON verbindet diese Idee mit einem persönlichen Assistenten und einer zentralen Übersicht.': ['We build software that takes recurring digital work off your hands. For freelancers, traders and companies who want to spend their time on more than routine. AURON brings this idea together with a personal assistant and one central overview.', 'Creamos software que te quita el trabajo digital repetitivo. Para autónomos, traders y empresas que quieren dedicar su tiempo a algo más que la rutina. AURON une esta idea con un asistente personal y una vista central.', 'Мы создаём софт, который снимает с тебя повторяющуюся цифровую работу. Для фрилансеров, трейдеров и компаний, которые хотят тратить время не только на рутину. AURON объединяет эту идею с личным ассистентом и единым обзором.', 'نطوّر برمجيات تخفف عنك العمل الرقمي المتكرر. للمستقلين والمتداولين والشركات الذين يريدون استثمار وقتهم في أكثر من الروتين. ويجمع AURON هذه الفكرة مع مساعد شخصي ونظرة مركزية واحدة.'],
    'Deine Fragen. Klar beantwortet.': ['Your questions. Clearly answered.', 'Tus preguntas. Respuestas claras.', 'Твои вопросы. Чёткие ответы.', 'أسئلتك. بإجابات واضحة.'],
    'Für wen lohnt sich AURON?': ['Who is AURON for?', '¿Para quién vale la pena AURON?', 'Кому подойдёт AURON?', 'لمن يناسب AURON؟'],
    'Für Selbstständige, Creator, Trader und kleine Teams, die regelmäßig Signale übertragen, Mails sortieren, Content vorbereiten oder Konten kontrollieren. Wie viel Zeit du sparst, hängt von deinen Abläufen und der Nutzung ab – je mehr Routine anfällt, desto mehr kann AURON dir abnehmen.': ['For freelancers, creators, traders and small teams who regularly copy signals, sort emails, prepare content or check accounts. How much time you save depends on your workflow – the more routine there is, the more AURON can take over.', 'Para autónomos, creadores, traders y equipos pequeños que copian señales, ordenan correos, preparan contenido o revisan cuentas. Cuánto tiempo ahorras depende de tu forma de trabajar – cuanta más rutina, más puede asumir AURON.', 'Для фрилансеров, креаторов, трейдеров и небольших команд, которые регулярно переносят сигналы, разбирают почту, готовят контент или проверяют счета. Сколько времени сэкономишь – зависит от твоих процессов: чем больше рутины, тем больше возьмёт на себя AURON.', 'للمستقلين وصنّاع المحتوى والمتداولين والفرق الصغيرة الذين ينقلون الإشارات أو يفرزون البريد أو يجهّزون المحتوى أو يراقبون الحسابات بانتظام. يعتمد الوقت الذي توفّره على طريقة عملك – فكلما زاد الروتين زاد ما يتولاه AURON.'],
    'Kann ich AURON erst testen?': ['Can I try AURON first?', '¿Puedo probar AURON primero?', 'Можно сначала попробовать AURON?', 'هل يمكنني تجربة AURON أولاً؟'],
    'Ja – 30 Tage kostenlos, mit allem, was dein Paket kann. Für den Kopierer empfehlen wir in dieser Zeit ein Demokonto.': ['Yes – 30 days free, with everything your plan includes. For the copier we recommend a demo account during that time.', 'Sí – 30 días gratis, con todo lo que incluye tu plan. Para el copiador recomendamos una cuenta demo en ese tiempo.', 'Да – 30 дней бесплатно со всеми возможностями тарифа. Для копировщика в это время советуем демо-счёт.', 'نعم – 30 يوماً مجاناً بكل ما تتضمنه باقتك. وننصح بحساب تجريبي للناسخ خلال هذه الفترة.'],
    'Lässt sich AURON an mein Geschäft anpassen?': ['Can AURON be adapted to my business?', '¿Se puede adaptar AURON a mi negocio?', 'Можно ли адаптировать AURON под мой бизнес?', 'هل يمكن تكييف AURON مع عملي؟'],
    'Ja, und zwar von dir selbst: Karten, Bereiche und Alarme stellst du im Dashboard ein, und beim Anschließen neuer Dienste führt dich AURON Schritt für Schritt – er sagt dir genau, was du tun musst. Wenn du es lieber abgibst, richten wir es für dich ein (Preis nach Aufwand).': ['Yes, by you: you set cards, areas and alerts in the dashboard, and when connecting new services AURON guides you step by step – it tells you exactly what to do. If you would rather hand it over, we set it up for you (priced by effort).', 'Sí, por ti mismo: ajustas tarjetas, áreas y alertas en el panel, y al conectar nuevos servicios AURON te guía paso a paso – te dice exactamente qué hacer. Si prefieres delegarlo, lo configuramos nosotros (precio según el trabajo).', 'Да, и сделать это можешь ты сам: карточки, разделы и оповещения настраиваются в дашборде, а при подключении новых сервисов AURON ведёт тебя шаг за шагом и точно говорит, что делать. Если хочешь передать это нам – настроим за тебя (цена по объёму).', 'نعم، وبنفسك: تضبط البطاقات والأقسام والتنبيهات في اللوحة، وعند ربط خدمات جديدة يرشدك AURON خطوة بخطوة ويخبرك بما عليك فعله بالضبط. وإن فضّلت تسليم الأمر، نُعدّه لك (السعر حسب الجهد).'],
    'Handelt AURON selbstständig?': ['Does AURON trade on its own?', '¿AURON opera por su cuenta?', 'Торгует ли AURON самостоятельно?', 'هل يتداول AURON من تلقاء نفسه؟'],
    'Nein – AURON ist dein Kontrolleur, kein Strategie-Automat. Er überwacht deine Konten, Gruppen und Bots, analysiert und beobachtet und hilft dir so bei deiner Strategie. Gebaut wird sie mit dir zusammen, mit Claude Code – auf Wunsch bis zum fertigen Bot für MetaTrader 5': ['No – AURON is your controller, not a strategy machine. It watches your accounts, groups and bots, analyses and observes, and so helps you with your strategy. You build it together, with Claude Code – up to a finished bot for MetaTrader 5 if you like', 'No – AURON es tu controlador, no una máquina de estrategias. Vigila tus cuentas, grupos y bots, analiza y observa, y así te ayuda con tu estrategia. La construyes con él, con Claude Code – hasta un bot terminado para MetaTrader 5 si quieres', 'Нет – AURON твой контролёр, а не автомат стратегий. Он следит за счетами, группами и ботами, анализирует и наблюдает и так помогает со стратегией. Строите вы её вместе, с Claude Code – при желании до готового бота для MetaTrader 5', 'لا – AURON مراقبك، وليس آلة استراتيجيات. يراقب حساباتك ومجموعاتك وروبوتاتك، ويحلل ويتابع، ويساعدك بذلك في استراتيجيتك. وتبنيانها معاً مع Claude Code – وحتى روبوت جاهز لميتاتريدر 5 إن أردت'],
    '. Handeln tun nur der Signal-Kopierer nach deinen Regeln und Bots, die du freigibst. Mails und Posts brauchen ebenfalls deine Freigabe.': ['. Only the signal copier trades, by your rules, and bots you approve. Emails and posts need your approval as well.', '. Solo opera el copiador de señales según tus reglas y los bots que apruebes. Correos y posts también necesitan tu aprobación.', '. Торгуют только копировщик сигналов по твоим правилам и боты, которые ты одобрил. Письма и посты тоже требуют одобрения.', '. لا يتداول إلا ناسخ الإشارات وفق قواعدك والروبوتات التي توافق عليها. والرسائل والمنشورات تحتاج موافقتك أيضاً.'],
    'Wo liegen meine Daten?': ['Where is my data?', '¿Dónde están mis datos?', 'Где хранятся мои данные?', 'أين توجد بياناتي؟'],
    'AURON läuft lokal auf deinem Rechner. Für verbundene Dienste nutzt du deine eigenen Zugänge. Wenn AURON mit Broker, Telegram oder Postfach arbeitet, werden die dafür nötigen Daten mit dem jeweiligen Dienst ausgetauscht.': ['AURON runs locally on your machine. For connected services you use your own logins. When AURON works with your broker, Telegram or inbox, the data needed for that is exchanged with that service.', 'AURON funciona en local en tu equipo. Para los servicios conectados usas tus propios accesos. Cuando AURON trabaja con tu bróker, Telegram o correo, se intercambian con ese servicio los datos necesarios.', 'AURON работает локально на твоём компьютере. Для подключённых сервисов ты используешь свои доступы. Когда AURON работает с брокером, Telegram или почтой, нужные данные передаются соответствующему сервису.', 'يعمل AURON محلياً على جهازك. وتستخدم حساباتك الخاصة للخدمات المرتبطة. وعندما يعمل AURON مع وسيطك أو تيليغرام أو بريدك، تُتبادل البيانات اللازمة مع تلك الخدمة فقط.'],
    'Kann AURON Mails in meinem Namen senden?': ['Can AURON send emails on my behalf?', '¿Puede AURON enviar correos en mi nombre?', 'Может ли AURON отправлять письма от моего имени?', 'هل يستطيع AURON إرسال رسائل باسمي؟'],
    'AURON nimmt dir das Formulieren ab und bereitet einen Entwurf vor. Du liest ihn durch, passt ihn bei Bedarf an und gibst den Versand ausdrücklich frei.': ['AURON does the wording and prepares a draft. You read it, adjust it if needed and explicitly approve sending it.', 'AURON redacta por ti y prepara un borrador. Tú lo lees, lo ajustas si hace falta y apruebas el envío expresamente.', 'AURON формулирует за тебя и готовит черновик. Ты читаешь, при необходимости правишь и явно разрешаешь отправку.', 'يتولى AURON الصياغة ويجهّز مسودة. تقرؤها وتعدّلها إن لزم وتوافق صراحة على الإرسال.'],
    'Welche Broker werden unterstützt?': ['Which brokers are supported?', '¿Qué brókers son compatibles?', 'Какие брокеры поддерживаются?', 'ما الوسطاء المدعومون؟'],
    'Der Signal-Kopierer ist für MetaTrader 5 vorgesehen. Ob dein konkreter Broker und Kontotyp unterstützt werden, sollte vor der Nutzung geprüft werden.': ['The signal copier is built for MetaTrader 5. Whether your specific broker and account type are supported should be checked before use.', 'El copiador de señales está pensado para MetaTrader 5. Conviene comprobar antes si tu bróker y tipo de cuenta son compatibles.', 'Копировщик сигналов рассчитан на MetaTrader 5. Поддержку конкретного брокера и типа счёта стоит проверить перед использованием.', 'ناسخ الإشارات مصمم لميتاتريدر 5. ويُستحسن التحقق قبل الاستخدام من دعم وسيطك ونوع حسابك تحديداً.'],
    'Risikohinweis:': ['Risk notice:', 'Aviso de riesgo:', 'Предупреждение о рисках:', 'تنبيه المخاطر:'],
    'Der Handel mit CFDs, Devisen und Kryptowährungen ist mit einem hohen Verlustrisiko verbunden, Hebel verstärkt Gewinne wie Verluste. Vergangene Ergebnisse sind kein Hinweis auf künftige. AURON ist ein Werkzeug, keine Anlageberatung.': ['Trading CFDs, forex and cryptocurrencies carries a high risk of loss; leverage amplifies gains and losses alike. Past results are no indication of future ones. AURON is a tool, not investment advice.', 'Operar con CFD, divisas y criptomonedas conlleva un alto riesgo de pérdida; el apalancamiento amplifica ganancias y pérdidas. Los resultados pasados no indican los futuros. AURON es una herramienta, no asesoramiento de inversión.', 'Торговля CFD, валютой и криптовалютами связана с высоким риском потерь; плечо усиливает и прибыль, и убытки. Прошлые результаты не говорят о будущих. AURON – инструмент, а не инвестиционный совет.', 'ينطوي تداول عقود الفروقات والعملات والعملات المشفرة على مخاطر خسارة عالية، والرافعة المالية تضاعف الأرباح والخسائر معاً. النتائج السابقة لا تدل على المستقبل. AURON أداة وليس نصيحة استثمارية.'],
    'Als Bild öffnen': ['Open as image', 'Abrir como imagen', 'Открыть как изображение', 'فتح كصورة'],
    'Schließen ✕': ['Close ✕', 'Cerrar ✕', 'Закрыть ✕', 'إغلاق ✕'],
    'Impressum': ['Legal notice', 'Aviso legal', 'Выходные данные', 'بيانات قانونية'],
    'Datenschutz': ['Privacy', 'Privacidad', 'Конфиденциальность', 'الخصوصية'],
    'AGB': ['Terms', 'Condiciones', 'Условия', 'الشروط'],
    '© 2026 Phoenix Life Solutions · Entwurf': ['© 2026 Phoenix Life Solutions · Draft', '© 2026 Phoenix Life Solutions · Borrador', '© 2026 Phoenix Life Solutions · Черновик', '© 2026 Phoenix Life Solutions · مسودة'],
    // the hero's looks (hero.js)
    'Am Wasserfall': ['By the waterfall', 'Junto a la cascada', 'У водопада', 'عند الشلال'],
    'In den Alpen': ['In the Alps', 'En los Alpes', 'В Альпах', 'في جبال الألب'],
    'Im eigenen Turm': ['In your own tower', 'En tu propia torre', 'В своей башне', 'في برجك الخاص'],
    'Über der Stadt': ['Above the city', 'Sobre la ciudad', 'Над городом', 'فوق المدينة'],
    'Klares Glas': ['Clear glass', 'Vidrio claro', 'Прозрачное стекло', 'زجاج شفاف'],
    'Verblasst · Grün': ['Faded · Green', 'Difuminado · Verde', 'Матовый · Зелёный', 'باهت · أخضر'],
    'Schwarze Karten · Gold': ['Black cards · Gold', 'Tarjetas negras · Oro', 'Чёрные карточки · Золото', 'بطاقات سوداء · ذهبي'],
    'Matt · Abendrot': ['Matte · Sunset', 'Mate · Atardecer', 'Матовый · Закат', 'مطفي · الغروب'],
    'Massiv · Champagner': ['Solid · Champagne', 'Sólido · Champán', 'Плотный · Шампань', 'صلب · شامباني'],
    'Klares Glas · Violett': ['Clear glass · Violet', 'Vidrio claro · Violeta', 'Прозрачное стекло · Фиолетовый', 'زجاج شفاف · بنفسجي'],
    '· Klares Glas': ['· Clear glass', '· Vidrio claro', '· Прозрачное стекло', '· زجاج شفاف'],
    'AURON – Weniger Routine. Mehr Zeit für dein Business.': ['AURON – Less routine. More time for your business.', 'AURON – Menos rutina. Más tiempo para tu negocio.', 'AURON – Меньше рутины. Больше времени для бизнеса.', 'AURON – روتين أقل. وقت أكثر لعملك.'],
  };
  const IDX = { en: 0, es: 1, ru: 2, ar: 3 };

  let lang = 'de';
  const t = (de) => (lang === 'de' || !T[de] ? de : T[de][IDX[lang]]);
  window.AURON_t = (de) => t(de);

  const textNodes = [];
  const attrNodes = [];
  function collect() {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => (n.parentElement.closest('script, style, svg') || !n.nodeValue.trim() ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
    });
    while (walker.nextNode()) {
      const n = walker.currentNode, raw = n.nodeValue, key = raw.replace(/\s+/g, ' ').trim();
      if (T[key]) textNodes.push({ n, key, lead: raw.match(/^\s*/)[0], tail: raw.match(/\s*$/)[0] });
    }
    document.querySelectorAll('[alt], [aria-label], [title]').forEach((el) => {
      ['alt', 'aria-label', 'title'].forEach((a) => { const v = el.getAttribute(a); if (v && T[v.trim()]) attrNodes.push({ el, a, key: v.trim() }); });
    });
  }

  function apply(next) {
    lang = LANGS[next] ? next : 'en';
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    textNodes.forEach(({ n, key, lead, tail }) => { n.nodeValue = lead + t(key) + tail; });
    attrNodes.forEach(({ el, a, key }) => el.setAttribute(a, t(key)));
    document.title = t('AURON – Weniger Routine. Mehr Zeit für dein Business.');
    document.querySelectorAll('.lang-btn b').forEach((b) => { b.textContent = lang.toUpperCase(); });
    document.querySelectorAll('.lang-menu button').forEach((b) => b.classList.toggle('on', b.dataset.lang === lang));
    try { localStorage.setItem('auron_lang', lang); } catch { /* private window */ }
    document.dispatchEvent(new CustomEvent('auron:lang', { detail: lang }));
  }

  function switcher() {
    const wrap = document.createElement('div');
    wrap.className = 'lang';
    wrap.innerHTML = `<button type="button" class="lang-btn" aria-haspopup="true" aria-label="Language">🌐 <b>EN</b></button>
      <div class="lang-menu" hidden>${Object.entries(LANGS).map(([k, n]) => `<button type="button" data-lang="${k}">${n}</button>`).join('')}</div>`;
    const menu = wrap.querySelector('.lang-menu');
    wrap.querySelector('.lang-btn').addEventListener('click', (e) => { e.stopPropagation(); menu.hidden = !menu.hidden; });
    menu.addEventListener('click', (e) => { const b = e.target.closest('[data-lang]'); if (b) { apply(b.dataset.lang); menu.hidden = true; } });
    document.addEventListener('click', () => { menu.hidden = true; });
    return wrap;
  }

  collect();
  document.querySelector('.nav')?.insertBefore(switcher(), document.querySelector('.nav .btn'));
  document.querySelector('.m-cta')?.appendChild(switcher());

  let saved = null;
  try { saved = localStorage.getItem('auron_lang'); } catch { /* private window */ }
  const fromUrl = new URLSearchParams(location.search).get('lang');
  const browser = (navigator.language || 'en').slice(0, 2).toLowerCase();
  apply(fromUrl || saved || (LANGS[browser] ? browser : 'en'));
})();
