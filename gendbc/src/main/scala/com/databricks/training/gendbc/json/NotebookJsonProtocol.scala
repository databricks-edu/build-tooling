package com.databricks.training.gendbc.json

import java.util.UUID

import com.databricks.training.gendbc.{Notebook, NotebookCell}
import spray.json.{JsArray, JsNumber, JsString, _}

/** This object contains the implicits that allow the parsed notebooks to
  * be converted to JSON, via the Spray JSON package. See
  * [[https://github.com/spray/spray-json#providing-jsonformats-for-other-types]]
  * for details on Spray JSON implicits.
  *
  * See [[https://github.com/databricks/training/blob/master/devops/courseware_build/dbc_format.md]]
  * for a discussion of the DBC JSON format. The JSON formats, below, are a
  * result of both that document's guidance and some reverse engineering of
  * DBC files.
  *
  * '''Note''': These converters only support writing JSON (i.e., conversion
  * ''to'' JSON). Converting back from JSON is not supported, because this tool
  * does not need that capability.
  */
object NotebookJsonProtocol extends DefaultJsonProtocol {

  /** JSON converter for a single notebook cell.
    */
  implicit object NotebookCellJsonFormat extends RootJsonFormat[NotebookCell] {
    def write(c: NotebookCell) = {
      JsObject(
        "bindings"          -> JsObject(),
        "collapsed"         -> JsBoolean(false),
        "command"           -> JsString(c.command),
        "commandTitle"      -> JsString(""),
        "commandType"       -> JsString("auto"),
        "commandVersion"    -> JsNumber(0),
        "commentThread"     -> JsArray(),
        "commentsVisible"   -> JsBoolean(false),
        "customPlotOptions" -> JsObject(),
        "diffDeletes"       -> JsArray(),
        "diffInserts"       -> JsArray(),
        "displayType"       -> JsString("table"),
        "error"             -> JsNull,
        "errorSummary"      -> JsNull,
        "finishTime"        -> JsNumber(0),
        "globalVars"        -> JsObject(),
        "guid"              -> JsString(c.guid.toString),
        "height"            -> JsString("auto"),
        "hideCommandCode"   -> JsBoolean(false),
        "hideCommandResult" -> JsBoolean(false),
        "iPythonMetadata"   -> JsNull,
        "inputWidgets"      -> JsObject(),
        "latestUser"        -> JsString(""),
        "nuid"              -> JsString(UUID.randomUUID.toString),
        "origId"            -> JsNumber(0),
        "parentHierarchy"   -> JsArray(),
        "pivotAggregation"  -> JsNull,
        "pivotColumns"      -> JsNull,
        "position"          -> JsNumber(c.position),
        "results"           -> JsNull,
        "showCommandTitle"  -> JsBoolean(false),
        "startTime"         -> JsNumber(0),
        "state"             -> JsString("finished"),
        "submitTime"        -> JsNumber(0),
        "subtype"           -> JsString("command"),
        "version"           -> JsString("CommandV1"),
        "width"             -> JsString("auto"),
        "workflows"         -> JsArray(),
        "xColumns"          -> JsNull,
        "yColumns"          -> JsNull
      )
    }

    def read(value: JsValue) = {
      deserializationError("Reading NotebookCell JSON is not supported.")
    }
  }

  /** JSON converter for a notebook.
    */
  implicit object NotebookJsonFormat extends RootJsonFormat[Notebook] {
    def write(n: Notebook) = {

      JsObject(
        "commands"        -> JsArray(n.cells.map(_.toJson)),
        "dashboards"      -> JsArray(),
        "globalVars"      -> JsObject(),
        "guid"            -> JsString(n.guid.toString),
        "iPythonMetadata" -> JsNull,
        "inputWidgets"    -> JsObject(),
        "language"        -> JsString(n.language),
        "name"            -> JsString(n.name),
        "origId"          -> JsNumber(0),
        "version"         -> JsString("NotebookV1")
      )
    }

    def read(value: JsValue) = {
      deserializationError("Reading Notebook JSON is not supported.")
    }
  }
}
