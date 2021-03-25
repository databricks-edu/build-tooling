function disableNav(page){
    var prevButton = document.getElementById("buttonPrevious");
    var nextButton = document.getElementById("buttonNext");

    if (page == 0){
        nextButton.disabled = false;
        prevButton.disabled = true;
    }
    else if (page == (pageArray.length - 1)){
        nextButton.disabled = true;
        prevButton.disabled = false;
    }
    else{
        nextButton.disabled = false;
        prevButton.disabled = false;
    }
}

function initializeStatus(){
    var completionStatus = ScormProcessGetValue("cmi.core.lesson_status");
    if (completionStatus == "not attempted") {
        ScormProcessSetValue("cmi.core.lesson_status", "incomplete");
    }
}

function getBookmark(){
    currentPage = 0;

    var bookmark = ScormProcessGetValue("cmi.core.lesson_location");

    if (bookmark != "") {
        if (confirm("Would you like to resume from where you previously left off?")) {
            currentPage = parseInt(bookmark, 10);
        }
        else currentPage = 0;
    }
}

function RecordQuiz(questionsFile){
    ScormProcessSetValue("cmi.objectives." + questionsFile + ".score.raw", 1)
}

function quizComplete(quizNumber){
  var quizResult = ScormProcessGetValue("cmi.objectives." + quizNumber + ".score.raw");
  return quizResult != "" ? 1 : 0;
}

function updateCompletion(){
    var quiz1 = quizComplete("1");
    var quiz2 = quizComplete("2");
    var quiz3 = quizComplete("3");
    var quiz4 = quizComplete("4");
    var quiz5 = quizComplete("5");
    var quiz6 = quizComplete("6");
    var quizzesPassed = quiz1 + quiz2 + quiz3 + quiz4 + quiz5 + quiz6;
    if (quizzesPassed > 4){
        ScormProcessSetValue("cmi.core.lesson_status", "completed");
    }
}

function goToPage(){

    var theIframe = document.getElementById("contentFrame");
    theIframe.src = pageArray[currentPage];
    ScormProcessSetValue("cmi.core.lesson_location", currentPage);
    disableNav(currentPage);
    if (currentPage < 7) {
      document.querySelectorAll(".sub-item").forEach(a=>a.style.display = "none");
      document.querySelectorAll(".group-1").forEach(a=>a.style.display = "block");
    } else
    if (currentPage < 14) {
      document.querySelectorAll(".sub-item").forEach(a=>a.style.display = "none");
      document.querySelectorAll(".group-2").forEach(a=>a.style.display = "block");
    } else
    if (currentPage < 20) {
      document.querySelectorAll(".sub-item").forEach(a=>a.style.display = "none");
      document.querySelectorAll(".group-3").forEach(a=>a.style.display = "block");
    } else
    if (currentPage < 26) {
      document.querySelectorAll(".sub-item").forEach(a=>a.style.display = "none");
      document.querySelectorAll(".group-4").forEach(a=>a.style.display = "block");
    } else
    if (currentPage < 30) {
      document.querySelectorAll(".sub-item").forEach(a=>a.style.display = "none");
      document.querySelectorAll(".group-5").forEach(a=>a.style.display = "block");
    } else
    if (currentPage < 34) {
      document.querySelectorAll(".sub-item").forEach(a=>a.style.display = "none");
      document.querySelectorAll(".group-6").forEach(a=>a.style.display = "block");
    } else {
      document.querySelectorAll(".sub-item").forEach(a=>a.style.display = "none");
      document.querySelectorAll(".group-7").forEach(a=>a.style.display = "block");
    }
}

function doUnload(pressedExit){

    //don't call this function twice
    if (processedUnload == true){return;}

    processedUnload = true;
    updateCompletion();

    //record the session time
    var endTimeStamp = new Date();
    var totalMilliseconds = (endTimeStamp.getTime() - startTimeStamp.getTime());
    var scormTime = ConvertMilliSecondsToSCORMTime(totalMilliseconds, false);

    ScormProcessSetValue("cmi.core.session_time", scormTime);

    //if the user just closes the browser, we will default to saving
    //their progress data. If the user presses exit, he is prompted.
    //If the user reached the end, the exit normall to submit results.
    if (pressedExit == false && reachedEnd == false){
        ScormProcessSetValue("cmi.core.exit", "suspend");
    }

    ScormProcessFinish();
}

function doPrevious(){
    if (currentPage > 0){
        currentPage--;
    }
    goToPage();
}

function doNext(){
    if (currentPage < (pageArray.length - 1)){
        currentPage++;
    }
    goToPage();
}

function doExit(){

    //note use of short-circuit AND. If the user reached the end, don't prompt.
    //just exit normally and submit the results.
    if (reachedEnd == false && confirm("Would you like to save your progress to resume later?")){
        //set exit to suspend
        ScormProcessSetValue("cmi.core.exit", "suspend");
    }
    else{
        //set exit to normal
        ScormProcessSetValue("cmi.core.exit", "");
    }

    //process the unload handler to close out the session.
    //the presense of an adl.nav.request will cause the LMS to
    //take the content away from the user.
    doUnload(true);

}
