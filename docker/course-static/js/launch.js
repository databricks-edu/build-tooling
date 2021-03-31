/*************************************/
//navigation functions
/*************************************/

var currentPage = null;
var startTimeStamp = null;
var processedUnload = false;
var reachedEnd = false;

/*************************************/
//functions for sizing the iFrame
/*************************************/
function setIframeDims(navWidth) {
    if ( document.getElementById ) {
        var theIframe = document.getElementById("contentFrame");
        var theContainer = document.getElementById("contentContainer");
        var boundingRect = theContainer.getBoundingClientRect();
        setIframeAttr(theIframe, boundingRect);
    }
}

function setIframeAttr(theIframe, boundingRect) {
    var width = boundingRect.width * .95;
    theIframe.style.height = "90%";
    theIframe.style.width = width + "px";
    theIframe.style.paddingLeft = Math.round((boundingRect.width - width)/2) + "px";
}

function launch(){
    startTimeStamp = new Date();
    setIframeDims();
    ScormProcessInitialize();
    initializeStatus()
    getBookmark()
    goToPage();
}

function checkKey(e) {
    e = e || window.event;
    if (e.keyCode == '37') { doPrevious(); }
    else if (e.keyCode == '39') { doNext(); }
}


window.onresize = setIframeDims;
document.onkeydown = checkKey;
