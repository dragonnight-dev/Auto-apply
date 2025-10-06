# Build Auto job apply

### summary
    This project is for auto job apply. so project consists of three main part. so first is the chrome extension to control the page and provide data to server. and second is the python server to receive the page data and process that and create the data to auto apply and send data to chrome extension. and the third is the server UI to show current state of the system and control the server such as synching url, auto fill the clients, current connection state, and state management( client enable, disable).
    All of the communication is by web socket, so server can send data to client at anytime.
    Backend server and React UI is running on docker.

## 1. Chrome extension - client

    0.1 sign up with user info such as resume and email, password
    0.2 sign in
    1.1 send page data(url or DOM data) to apply
    1.2 receive page data from server
    1.3 control(sync url, get data, get url, click buttons and auto fill, upload resume) with the data from server at the page

## 2. Python backend( DJango + AI ) - server

### python backend uses AI ( SLM )
        1. tool fallback,
        2. rewrite the Resume, create the text that request

    0.1     sign up(AI extract the structured data from user info and resume, structured data are stored in PostgreSql and save the resume with named the DB/[email].pdf at the Docker container)
    0.2     sign in : at this time the client and server web socket connection is created.
    1.1     retrieve url from client and display at the table.
    1.2     if click the sync url button, sync url with selected url at all of the clients and get DOM data from one client.
    1.3     from DOM data and each enabled client info, AI created data to auto fill. : SLM user tool fallback and create text from structured data and JD and requested question.
    1.4     if click auto fill data button, then each created auto fill data(upload resume) are sent to client(chrome extension) and retrieve the results.
    2.1     save the history(client, apply_url, time, results)
    2.2     show, delete history.

## 3. React UI
    0.1 sign up with boss key.
    1.1 display the connected client state(url, current action - syncing, filling, no-action)
    1.2 when hover the row, appears the sync button and click sync button, then all connected clients sync urls with selected url.
    1.3 when click fill data, then send created data to clients and show the results.
    2.1 display and manage the stochastic of each clients(history: url, time, results).

# Instructions
    use local open-weight SLM from the Huggingface or other web site.
    the model size should be about 4GB and the accuracy should be best.
    and the model handle only English.

    the chrome extension is installed other PCs and server has to be running on my local docker.


rule:
    set the date time to 10/6/2025 8:00:00 A.M.
    create the project step by step follow the logic.
    create the test code.
    create commit for each component or unit.
    change the time and commit and do next working.
    if the date is changed, create pull request.
    if the time is over 17:00:00 P.M, set date to next day 8:00:00 A.M.

I have already given you the permission.
    