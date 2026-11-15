<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<!DOCTYPE html>
<html dir="rtl" lang="fa">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex, nofollow">
    <meta name="color-scheme" content="light dark">
    <title>${msg("loginTitle",(realm.displayName!''))}</title>
    <link rel="stylesheet" href="${url.resourcesPath}/css/login.css">
</head>
<body>
<main class="sp-shell">
    <section class="sp-card" aria-labelledby="kc-page-title">
        <div class="sp-brand">
            <svg class="sp-mark" viewBox="0 0 40 40" aria-hidden="true" focusable="false">
                <rect width="40" height="40" rx="12" fill="currentColor"/>
                <text x="20" y="26" text-anchor="middle" fill="var(--sp-mark-ink)" font-family="Vazirmatn, Tahoma, sans-serif" font-size="15" font-weight="700">SP</text>
            </svg>
            <p class="sp-word">StockPilot</p>
            <p class="sp-tagline">سامانه مدیریت سفارش و موجودی برای شرکت‌های پخش</p>
        </div>

        <h1 id="kc-page-title"><#nested "header"></h1>

        <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
            <div class="sp-alert sp-alert-${message.type}" role="alert">
                <span>${kcSanitize(message.summary)?no_esc}</span>
            </div>
        </#if>

        <#nested "form">
        <#nested "info">
        <#nested "socialProviders">
    </section>
</main>
</body>
</html>
</#macro>
