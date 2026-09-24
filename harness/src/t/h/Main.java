package t.h;
import android.app.Activity;
import android.os.Bundle;
import android.text.InputType;
import android.widget.EditText;
import android.widget.LinearLayout;
/** Empty text field for keyboard tests: no prefill, no suggestions from the app itself. */
public class Main extends Activity {
  @Override protected void onCreate(Bundle b) {
    super.onCreate(b);
    LinearLayout l = new LinearLayout(this);
    l.setOrientation(LinearLayout.VERTICAL);
    EditText e = new EditText(this);
    e.setContentDescription("harness-field");
    e.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
    e.setMinLines(4);
    l.addView(e);
    setContentView(l);
    e.requestFocus();
  }
}
