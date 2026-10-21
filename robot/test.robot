*** Settings ***
Library    SeleniumLibrary
Library    OperatingSystem
Library    Process
Library    ${CURDIR}${/}..${/}scripts${/}time_range.py

*** Variables ***
${URL}             https://e.samator.com/one/monitoring/grafana/d/bf5ymm8nzu134b/4-one-service-log?var-env=prod
${BROWSER}         chrome
${USERNAME}        admin
${PASSWORD}        %{GRAFANA_PASSWORD}
${TIMEOUT}         30s
${FROM_TIME}       ${EMPTY}
${TO_TIME}         ${EMPTY}

*** Test Cases ***
Download Grafana CSV and Process Latest File
    [Documentation]    Log in to Grafana, open the time picker, and apply the requested absolute range.
    ${start}    ${cutoff}=    Resolve Time Range    ${FROM_TIME}    ${TO_TIME}
    ${FROM_TIME}=    Evaluate    $start.strftime('%Y-%m-%d %H:%M:%S')
    ${TO_TIME}=    Evaluate    $cutoff.strftime('%Y-%m-%d %H:%M:%S')
    Log To Console    Rentang WIB: ${FROM_TIME} -> ${TO_TIME}
    ${chrome_options}=    Evaluate    __import__('selenium').webdriver.ChromeOptions()
    ${download_directory}=    Normalize Path    ${CURDIR}${/}..${/}data${/}downloads
    Create Directory    ${download_directory}
    ${download_prefs}=    Create Dictionary    download.default_directory=${download_directory}    download.prompt_for_download=${False}    download.directory_upgrade=${True}    safebrowsing.enabled=${True}
    Call Method    ${chrome_options}    add_experimental_option    prefs    ${download_prefs}
    Call Method    ${chrome_options}    add_experimental_option    detach    ${True}
    Open Browser    ${URL}    ${BROWSER}    options=${chrome_options}
    Log To Console    Membuka Grafana dan login...
    Set Window Size    1440    1000

    # Log in if Grafana presents its sign-in page.
    ${login_visible}=    Run Keyword And Return Status    Wait Until Element Is Visible    name=user    timeout=5s
    IF    ${login_visible}
        Input Text    name=user    ${USERNAME}
        Input Password    name=password    ${PASSWORD}
        Click Button    xpath=//button[@type='submit']
    END

    Wait Until Location Contains    bf5ymm8nzu134b    timeout=${TIMEOUT}

    # The URL selects prod; wait for the dashboard to confirm it.
    Wait Until Element Is Visible    xpath=//*[@data-testid='data-testid header-container'][contains(normalize-space(.),'Console Log (prod)')]    timeout=${TIMEOUT}
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
    ${expected_from}=    Evaluate    str(int($start.timestamp() * 1000))
    ${expected_to}=    Evaluate    str(int($cutoff.timestamp() * 1000))
    Wait Until Keyword Succeeds    10s    500ms    Grafana Range Should Match    ${expected_from}    ${expected_to}
    # Hover over the Console Log panel header to reveal its controls.
    Log To Console    Menerapkan filter log Yeastar...
    Wait Until Element Is Visible    xpath=//*[@data-testid='data-testid header-container'][contains(normalize-space(.),'Console Log')]    timeout=${TIMEOUT}
    Mouse Over    xpath=//*[@data-testid='data-testid header-container'][contains(normalize-space(.),'Console Log')]
    # Open the panel menu, then click Inspect and Panel JSON.
    ${panel_menu_button}=    Set Variable    css:button[data-testid^="data-testid Panel menu"]
    Click Element    ${panel_menu_button}
    Wait Until Element Is Visible    css:[data-testid="data-testid Panel menu item Inspect"]    timeout=${TIMEOUT}
    Wait Until Keyword Succeeds    3x    1s    Open Inspect Submenu Item    css:[data-testid="data-testid Panel menu item Panel JSON"]
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
    Wait Until Keyword Succeeds    3x    1s    Open Inspect Submenu Item    xpath=//*[@role='menuitem' and normalize-space(.)='Data']
    Wait Until Element Is Visible    xpath=//button[normalize-space(.)='Download CSV']    timeout=${TIMEOUT}
    ${previous_csvs}=    List Files In Directory    ${download_directory}    *.csv
    Log To Console    Mengunduh CSV dan menunggu unduhan selesai...
    Click Element    xpath=//button[normalize-space(.)='Download CSV']
    ${downloaded_csv}=    Wait Until Keyword Succeeds    120s    1s    CSV Download Should Be Complete    ${download_directory}    ${previous_csvs}
    ${python}=    Evaluate    sys.executable    modules=sys
    ${result}=    Run Process    ${python}    ${CURDIR}${/}..${/}scripts${/}join.py    ${downloaded_csv}    timeout=120s    on_timeout=terminate
    Log    ${result.stdout}
    Log To Console    ${result.stdout}
    Should Be Equal As Integers    ${result.rc}    0    msg=${result.stderr}
    ${range_json}=    Evaluate    json.dumps({'from': $FROM_TIME, 'to': $TO_TIME, 'timezone': 'Asia/Jakarta'})    modules=json
    Create File    ${CURDIR}${/}..${/}data${/}processed${/}time_range.json    ${range_json}

*** Keywords ***
Grafana Range Should Match
    [Arguments]    ${expected_from}    ${expected_to}
    ${location}=    Get Location
    ${query}=    Evaluate    urllib.parse.parse_qs(urllib.parse.urlparse($location).query)    modules=urllib.parse
    ${actual_from}=    Evaluate    str(int(datetime.datetime.fromisoformat($query['from'][0].replace('Z', '+00:00')).timestamp() * 1000)) if not $query['from'][0].isdigit() else $query['from'][0]    modules=datetime
    ${actual_to}=    Evaluate    str(int(datetime.datetime.fromisoformat($query['to'][0].replace('Z', '+00:00')).timestamp() * 1000)) if not $query['to'][0].isdigit() else $query['to'][0]    modules=datetime
    Should Be Equal    ${actual_from}    ${expected_from}
    Should Be Equal    ${actual_to}    ${expected_to}

Open Inspect Submenu Item
    [Arguments]    ${item}
    Mouse Over    css:[data-testid="data-testid Panel menu item Inspect"]
    Wait Until Element Is Visible    ${item}    timeout=3s
    ${element}=    Get WebElement    ${item}
    Execute Javascript    arguments[0].click();    ARGUMENTS    ${element}

CSV Download Should Be Complete
    [Arguments]    ${directory}    ${previous_csvs}
    ${partial}=    List Files In Directory    ${directory}    *.crdownload
    Should Be Empty    ${partial}
    ${current_csvs}=    List Files In Directory    ${directory}    *.csv
    ${new_csvs}=    Evaluate    set($current_csvs) - set($previous_csvs) - {'merged.csv'}
    Should Not Be Empty    ${new_csvs}    CSV baru belum selesai diunduh.
    Length Should Be    ${new_csvs}    1
    FOR    ${filename}    IN    @{new_csvs}
        ${size}=    Get File Size    ${directory}${/}${filename}
        Should Be True    ${size} > 0
    END
    ${filename}=    Evaluate    next(iter($new_csvs))
    RETURN    ${directory}${/}${filename}
