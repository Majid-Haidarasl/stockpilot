<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username','password') displayInfo=false; section>
    <#if section = "header">
        ${msg("loginAccountTitle")}
    <#elseif section = "form">
        <div id="kc-form">
            <div id="kc-form-wrapper">
                <#if realm.password>
                    <form id="kc-form-login" action="${url.loginAction}" method="post">
                        <#if !usernameHidden??>
                            <div class="sp-field">
                                <label for="username">
                                    <#if !realm.loginWithEmailAllowed>${msg("username")}<#elseif !realm.registrationEmailAsUsername>${msg("usernameOrEmail")}<#else>${msg("email")}</#if>
                                </label>
                                <input tabindex="1" id="username" name="username" value="${(login.username!'')}" type="text" autofocus autocomplete="username" dir="ltr"
                                       aria-invalid="<#if messagesPerField.existsError('username','password')>true<#else>false</#if>"
                                       <#if messagesPerField.existsError('username','password')>aria-describedby="input-error"</#if>>
                            </div>
                        </#if>

                        <div class="sp-field">
                            <label for="password">${msg("password")}</label>
                            <div class="sp-password">
                                <input tabindex="2" id="password" name="password" type="password" autocomplete="current-password" dir="ltr"
                                       aria-invalid="<#if messagesPerField.existsError('username','password')>true<#else>false</#if>"
                                       <#if messagesPerField.existsError('username','password')>aria-describedby="input-error"</#if>>
                                <button type="button" class="sp-eye" data-password-toggle aria-label="${msg('showPassword')}" aria-controls="password" aria-pressed="false" tabindex="3">
                                    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                                        <path fill="currentColor" d="M12 5c5.2 0 9.3 3.4 10.8 7-1.5 3.6-5.6 7-10.8 7S2.7 15.6 1.2 12C2.7 8.4 6.8 5 12 5zm0 2C8.1 7 5.1 9.5 3.8 12 5.1 14.5 8.1 17 12 17s6.9-2.5 8.2-5C18.9 9.5 15.9 7 12 7zm0 1.8A3.2 3.2 0 1 1 12 15.2 3.2 3.2 0 0 1 12 8.8z"/>
                                    </svg>
                                </button>
                            </div>
                        </div>

                        <#if messagesPerField.existsError('username','password')>
                            <p id="input-error" class="sp-alert sp-alert-error" role="alert">
                                ${kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc}
                            </p>
                        </#if>

                        <div id="kc-form-buttons">
                            <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth?? && auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>>
                            <input tabindex="4" id="kc-login" name="login" type="submit" value="${msg('doLogIn')}">
                        </div>
                    </form>
                    <script>
                        (function () {
                            var button = document.querySelector("[data-password-toggle]");
                            var input = document.getElementById("password");
                            if (!button || !input) return;
                            var showLabel = "نمایش رمز";
                            var hideLabel = "پنهان کردن رمز";
                            button.addEventListener("click", function () {
                                var reveal = input.type === "password";
                                input.type = reveal ? "text" : "password";
                                button.setAttribute("aria-pressed", reveal ? "true" : "false");
                                button.setAttribute("aria-label", reveal ? hideLabel : showLabel);
                            });
                        })();
                    </script>
                </#if>
            </div>
        </div>
    </#if>
</@layout.registrationLayout>
