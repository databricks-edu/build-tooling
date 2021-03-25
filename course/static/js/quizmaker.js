var QUESTION_TYPE_CHOICE = "choice";
var QUESTION_TYPE_TF = "true-false";
var QUESTION_TYPE_NUMERIC = "numeric";

function Question(id, text, type, answers, correctAnswer, objectiveId){
    this.Id = id;
    this.Text = text;
    this.Type = type;
    this.Answers = answers;
    this.CorrectAnswer = correctAnswer;
    this.ObjectiveId = objectiveId;
}

function Test(questions){
    this.Questions = questions;
}
Test.prototype.AddQuestion = function(question)
{
    this.Questions[this.Questions.length] = question;
}

var test = new Test(new Array());

var questionsFile = getQueryParam("questions");
document.write('<script src="html/quiz/questions-', questionsFile, '.js" type="text/JavaScript"><\/script>');

function CheckNumeric(obj){
    var userText = new String(obj.value);
    var numbersRegEx = /[^0-9]/g;
    if (userText.search(numbersRegEx) >= 0){
        alert("Please enter only numeric values.");
        obj.value = userText.replace(numbersRegEx, "");
    }
}
function SubmitAnswers(){
    var correctCount = 0;
    var totalQuestions = test.Questions.length;

    var resultsSummary = "";

    for (var i in test.Questions){
        var question = test.Questions[i];

        var wasCorrect = false;
        var correctAnswer = null;
        var learnerResponse = "";

        switch (question.Type){
            case QUESTION_TYPE_CHOICE:

                for (var answerIndex = 0; answerIndex < question.Answers.length; answerIndex++){

                    if (question.CorrectAnswer == question.Answers[answerIndex]){
                        correctAnswer = answerIndex;
                    }
                    if (document.getElementById("question_" + question.Id + "_" + answerIndex).checked == true){
                        learnerResponse = answerIndex;
                    }
                }

            break;

            case QUESTION_TYPE_TF:

                if (document.getElementById("question_" + question.Id + "_True").checked == true){
                    learnerResponse = "true";
                }
                if (document.getElementById("question_" + question.Id + "_False").checked == true){
                   learnerResponse = "false";
                }

                if (question.CorrectAnswer == true){
                    correctAnswer = "true";
                }
                else{
                    correctAnswer = "false";
                }
            break;

            case QUESTION_TYPE_NUMERIC:
                correctAnswer = question.CorrectAnswer;
                learnerResponse = document.getElementById("question_" + question.Id + "_Text").value;
            break;

            default:
                alert("invalid question type detected");
            break;
        }

        wasCorrect = (correctAnswer == learnerResponse);
        if (wasCorrect) {correctCount++;}

        if (parent.RecordQuestion){
            parent.RecordQuestion(test.Questions[i].Id,
                                    test.Questions[i].Text,
                                    test.Questions[i].Type,
                                    learnerResponse,
                                    correctAnswer,
                                    wasCorrect,
                                    test.Questions[i].ObjectiveId);
        }

        resultsSummary += "<div class='questionResult'><h3>Question " + i + "</h3>";
        if (wasCorrect) {
            resultsSummary += "<em>Correct</em><br>"
        }
        else{
            resultsSummary += "<em>Incorrect</em><br>"
            resultsSummary += "Your answer: " + learnerResponse + "<br>"
            resultsSummary += "Correct answer: " + correctAnswer + "<br>"
        }
        resultsSummary += "</div>";
    }
    var score = Math.round(correctCount * 100 / totalQuestions);
    resultsSummary = "<h3>Score: " + score + "</h3>" + resultsSummary;
    document.getElementById("test").innerHTML = resultsSummary;

  if (parent.RecordQuiz){
      parent.RecordQuiz(questionsFile);
    }
}

function RenderTest(test){

    document.write ("<div id='test'><form id='frmTest' action='#'>");

    for (var i in test.Questions){
        var question = test.Questions[i];

        document.write ("<div id='question_" + question.Id + "' class='question'>");
        document.write (question.Text);

        switch (question.Type){
            case QUESTION_TYPE_CHOICE:
                var ansIndex = 0;
                for (var j in question.Answers){
                    var answer = question.Answers[j];
                    document.write("<div ");
                    if (question.CorrectAnswer == answer) {document.write("class='correctAnswer'");} else{document.write("class='answer'");}
                    document.write("><input type='radio' name='question_" + question.Id + "_choices' id='question_" + question.Id + "_" + ansIndex + "'/>" + answer + "</div>");
                    ansIndex++;
                }
            break;

            case QUESTION_TYPE_TF:

                document.write("<div ");
                if (question.CorrectAnswer == true) {document.write("class='correctAnswer'");}else{document.write("class='answer'");}
                document.write("><input type='radio' name='question_" + question.Id + "_choices' id='question_" + question.Id + "_True'/>True</div>");

                document.write("<div ");
                if (question.CorrectAnswer == false) {document.write("class='correctAnswer'");}else{document.write("class='answer'");}
                document.write("><input type='radio' name='question_" + question.Id + "_choices' id='question_" + question.Id + "_False'/>False</div>");
            break;

            case QUESTION_TYPE_NUMERIC:
                document.write("<div class='correctAnswer'><input type='text' value='' id='question_" + question.Id + "_Text' onchange='CheckNumeric(this)'/> (");
                document.write(question.CorrectAnswer + ")</div>");
            break;

            default:
                alert("invalid question type detected");
            break;
        }
        document.write ("</div>");      //close out question div
    }
    document.write("<input type='button' value='Submit Answers' onclick='SubmitAnswers();' />");
    document.write ("</form></div>");      //close out test div
}

function getQueryParam(key) {
    var vars = [], hash;
    var hashes = window.location.href.slice(window.location.href.indexOf('?') + 1).split('&');
    for(var i = 0; i < hashes.length; i++)
    {
        hash = hashes[i].split('=');
        vars.push(hash[0]);
        vars[hash[0]] = hash[1];
    }
    return vars[key];
}
