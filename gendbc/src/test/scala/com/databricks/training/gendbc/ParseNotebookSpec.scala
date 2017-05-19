package com.databricks.training.gendbc

import java.io.{File, FileWriter}

import scala.io.Source

import grizzled.util.CanReleaseResource.Implicits.CanReleaseAutoCloseable
import grizzled.util.CanReleaseResource.Implicits.CanReleaseSource

class ParseNotebookSpec extends BaseSpec {

  import grizzled.sys.{os, OperatingSystem}

  val GoodNotebook     = "GoodNotebook1.scala"
  val EmptyNotebook    = "EmptyNotebook.scala"
  val NoHeaderNotebook = "NoHeaderNotebook.scala"

  def leadingPath(f: File): String = {
    os match {
      case OperatingSystem.Windows =>
        val driveLetter = f.getPath.headOption.getOrElse("C")
        s"$driveLetter:\\"
      case _ => "/"
    }
  }

  "Notebook.parse()" should "properly parse a valid notebook" in {
    withJarResourceAsFile(GoodNotebook) { file =>
      val t = Notebook.parse(file            = file,
                             dbcFolder       = None,
                             encoding        = "ISO-8859-1",
                             trimLeadingPath = leadingPath(file))
      t should be (success)
      val nb = t.get
      nb.cells.length should be > 1
      nb.cells(0).command should startWith("%md")
      nb.cells.count(s => !s.command.contains("%md")) should be > 0
    }
  }

  it should "fail on an empty notebook" in {
    withJarResourceAsFile(EmptyNotebook) { file =>
      val t = Notebook.parse(file            = file,
                             dbcFolder       = None,
                             encoding        = "ISO-8859-1",
                             trimLeadingPath = leadingPath(file))
      t should be (failure)
    }
  }

  it should "fail on a notebook that lacks the Databricks header" in {
    withJarResourceAsFile(NoHeaderNotebook) { file =>
      val t = Notebook.parse(file            = file,
                             dbcFolder       = None,
                             encoding        = "ISO-8859-1",
                             trimLeadingPath = leadingPath(file))
      t should be (failure)
    }
  }

  def withJarResourceAsFile(resource: String)(code: File => Unit): Unit = {
    import grizzled.file.util.{withTemporaryDirectory, joinPath}
    import grizzled.util.withResource

    val cl = getClass.getClassLoader
    withTemporaryDirectory("nb") { dir =>
      val tempFile = new File(joinPath(dir.getPath, "notebook.scala"))
      withResource(Source.fromInputStream(cl.getResourceAsStream(resource))) { src =>
        withResource(new FileWriter(tempFile)) { out =>
          out.write(src.mkString)
        }
      }

      code(tempFile)
    }
  }
}
