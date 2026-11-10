const fs = require('node:fs');

// A runner-owned results folder is created fresh for each session. Only the
// explicit finish token ends the wait; stdin EOF and elapsed time never do.
function waitForManualFinish(app, signalFile) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (reason, error) => {
      if (settled) return;
      settled = true;
      fs.unwatchFile(signalFile, check);
      app.off('close', onClose);
      if (error) reject(error); else resolve(reason);
    };
    const onClose = () => finish('window_closed');
    const check = async () => {
      if (settled) return;
      try {
        const value = await fs.promises.readFile(signalFile, 'utf8');
        if (value.trim() === 'finish') finish('finish_file');
      } catch (error) {
        if (error.code !== 'ENOENT') finish(undefined, error);
      }
    };
    app.once('close', onClose);
    fs.watchFile(signalFile, { interval: 100 }, check);
    void check();
  });
}

module.exports = { waitForManualFinish };
