*** Settings ***
Library    SeleniumLibrary

*** Variables ***
${URL}             https://e.samator.com/one/monitoring/grafana/d/bf5ymm8nzu134b/4-one-service-log?var-env=test
${BROWSER}         chrome
${USERNAME}        admin
${PASSWORD}        %{GRAFANA_PASSWORD}
${FROM_TIME}       2026-10-20 00:00:00
${TO_TIME}         2026-10-21 23:59:59
${TIMEOUT}         30s

*** Test Cases ***
Set Grafana Time Range
    [Documentation]    Log in to Grafana, open the time picker, and apply the requested absolute range.
    ${chrome_options}=    Evaluate    __import__('selenium').webdriver.ChromeOptions()
    ${download_prefs}=    Create Dictionary    download.default_directory=D:/MAGANG/grafana/robot    download.prompt_for_download=${False}    download.directory_upgrade=${True}    safebrowsing.enabled=${True}
    Call Method    ${chrome_options}    add_experimental_option    prefs    ${download_prefs}
    Call Method    ${chrome_options}    add_experimental_option    detach    ${True}
    Open Browser    ${URL}    ${BROWSER}    options=${chrome_options}
    Maximize Browser Window

    # Log in if Grafana presents its sign-in page.
    ${login_visible}=    Run Keyword And Return Status    Wait Until Element Is Visible    name=user    timeout=5s
    IF    ${login_visible}
        Input Text    name=user    ${USERNAME}
        Input Password    name=password    ${PASSWORD}
        Click Button    xpath=//button[@type='submit']
    END

    Wait Until Location Contains    bf5ymm8nzu134b    timeout=${TIMEOUT}

    # Wait for the dashboard variables to render, then select prod.
    ${env_combobox}=    Set Variable    css:[role="combobox"][data-testid^="data-testid Dashboard template variables Variable Value DropDown value link text"]
    Wait Until Element Is Visible    ${env_combobox}    timeout=${TIMEOUT}
    Click Element    ${env_combobox}
    Wait Until Element Is Visible    xpath=//*[@role='option' and normalize-space(.)='prod']    timeout=${TIMEOUT}
    Click Element    xpath=//*[@role='option' and normalize-space(.)='prod']
    # Open the time-range picker after successful login.
    Wait Until Element Is Visible    css:button[data-testid="data-testid TimePicker Open Button"]    timeout=${TIMEOUT}
    Click Element    css:button[data-testid="data-testid TimePicker Open Button"]

    # The Absolute time range fields are already expanded in this Grafana view.
    Wait Until Element Is Visible    css:input[data-testid="data-testid Time Range from field"]    timeout=${TIMEOUT}
    Wait Until Element Is Visible    css:input[data-testid="data-testid Time Range to field"]    timeout=${TIMEOUT}
    Input Text    css:input[data-testid="data-testid Time Range from field"]    ${FROM_TIME}
    Input Text    css:input[data-testid="data-testid Time Range to field"]    ${TO_TIME}

    # Apply the absolute time range.
    Wait Until Element Is Enabled    css:button[data-testid="data-testid TimePicker submit button"]    timeout=${TIMEOUT}
    Click Element    css:button[data-testid="data-testid TimePicker submit button"]
    Wait Until Page Contains    ${FROM_TIME}    timeout=${TIMEOUT}
    # Hover over the Console Log panel header to reveal its controls.
    Wait Until Element Is Visible    xpath=//*[@data-testid='data-testid header-container'][contains(normalize-space(.),'Console Log')]    timeout=${TIMEOUT}
    Mouse Over    xpath=//*[@data-testid='data-testid header-container'][contains(normalize-space(.),'Console Log')]
    # Open the panel menu, then click Inspect and Panel JSON.
    ${panel_menu_button}=    Set Variable    css:button[data-testid^="data-testid Panel menu"]
    Click Element    ${panel_menu_button}
    Sleep    2s
    Click Element    css:[data-testid="data-testid Panel menu item Inspect"]
    Sleep    2s
    Click Element    css:[data-testid="data-testid Panel menu item Panel JSON"]
    Sleep    2s
    # Wait for Monaco to load, navigate to line 25, replace it, then apply.
    Wait Until Element Is Visible    css:.monaco-editor .view-lines    timeout=${TIMEOUT}
    Click Element    css:.monaco-editor .view-lines
    Press Keys    ${None}    CTRL+g
    Press Keys    ${None}    25
    Press Keys    ${None}    ENTER
    Press Keys    ${None}    HOME
    Press Keys    ${None}    SHIFT+END
    Press Keys    ${None}    BACKSPACE
    ${expr_line}=    Evaluate    '"expr": "{env=' + chr(92) + '"$env' + chr(92) + '"} != `/metrics` != `/health-status` |= `Yeastar RAW body`",'
    Press Keys    ${None}    ${expr_line}
    Click Element    xpath=//button[normalize-space(.)='Apply']

    # Reopen the Console Log panel inspector and download its CSV data.
    Wait Until Element Is Visible    xpath=//*[@data-testid='data-testid header-container'][contains(normalize-space(.),'Console Log')]    timeout=${TIMEOUT}
    Mouse Over    xpath=//*[@data-testid='data-testid header-container'][contains(normalize-space(.),'Console Log')]
    Wait Until Element Is Visible    ${panel_menu_button}    timeout=${TIMEOUT}
    Click Element    ${panel_menu_button}
    ${inspect_menu_item}=    Set Variable    css:[data-testid="data-testid Panel menu item Inspect"]
    Wait Until Element Is Visible    ${inspect_menu_item}    timeout=${TIMEOUT}
    Mouse Over    ${inspect_menu_item}
    Wait Until Element Is Visible    xpath=//*[@role='menuitem' and normalize-space(.)='Data']    timeout=${TIMEOUT}
    Click Element    xpath=//*[@role='menuitem' and normalize-space(.)='Data']
    Wait Until Element Is Visible    xpath=//button[normalize-space(.)='Download CSV']    timeout=${TIMEOUT}
    Click Element    xpath=//button[normalize-space(.)='Download CSV']










