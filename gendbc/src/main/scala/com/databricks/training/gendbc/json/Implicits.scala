package com.databricks.training.gendbc.json

import spray.json.JsValue

import scala.util.Try

/** Implicit decorator classes for Spray JSON.
  */
object Implicits {

  /** Enrichment class for Spray JSON `JsValue`.
    */
  implicit class RichJsValue(js: JsValue) {

    /** Convert this JSON AST to a byte buffer in the specified character
      * set.
      *
      * @param charsetName the character set name
      *
      * @return A `Success` containing the resulting byte array, or a
      *         `Failure` if the character set name is invalid or the JSON
      *         cannot be encoded in the specified character set.
      */
    def toCharset(charsetName: String): Try[Array[Byte]] = {
      import java.nio.charset.Charset
      import java.nio.CharBuffer

      for { encoder <- Try { Charset.forName(charsetName).newEncoder }
            buf     <- Try { encoder.encode(CharBuffer.wrap(js.toString)) } }
      yield buf.array
    }
  }
}
