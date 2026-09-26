package test.clip.fixture;
import android.app.Activity;
import android.os.Bundle;
import android.os.PersistableBundle;
import android.content.ClipData;
import android.content.ClipDescription;
import android.content.ClipboardManager;
import android.content.Context;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
public final class MainActivity extends Activity {
  static final String UNMARKED = "ordinary.probe@example.test";
  static final String MARKED = "marked.probe@example.test";
  static final String MARKED_ON = "marked-on.probe@example.test";
  void copy(String text, boolean sensitive) {
    ClipData clip=ClipData.newPlainText("probe",text);
    if (sensitive) {
      PersistableBundle extras=new PersistableBundle();
      extras.putBoolean(ClipDescription.EXTRA_IS_SENSITIVE,true);
      clip.getDescription().setExtras(extras);
    }
    ((ClipboardManager)getSystemService(Context.CLIPBOARD_SERVICE)).setPrimaryClip(clip);
  }
  @Override public void onCreate(Bundle state) {
    super.onCreate(state);
    LinearLayout layout=new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL);
    Button a=new Button(this);a.setText("Copy unmarked email");a.setContentDescription("Copy unmarked email");
    a.setOnClickListener(v->copy(UNMARKED,false));layout.addView(a);
    Button b=new Button(this);b.setText("Copy app-marked email");b.setContentDescription("Copy app-marked email");
    b.setOnClickListener(v->copy(MARKED,true));layout.addView(b);
    Button c=new Button(this);c.setText("Copy distinct app-marked email");c.setContentDescription("Copy distinct app-marked email");
    c.setOnClickListener(v->copy(MARKED_ON,true));layout.addView(c);
    EditText edit=new EditText(this);edit.setSingleLine(true);edit.setHint("Tap here for keyboard clipboard");
    layout.addView(edit);setContentView(layout);
  }
}
